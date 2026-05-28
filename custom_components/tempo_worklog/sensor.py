"""Tempo Worklog sensor — tracks logged hours via Tempo Cloud API v4."""
import logging
from datetime import date, timedelta

from homeassistant.util import dt as dt_util

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_ACCOUNT_ID,
    CONF_MIN_HOURS,
    CONF_WEEKLY_HOURS,
    DEFAULT_BASE_URL,
    DEFAULT_MIN_HOURS,
    DEFAULT_WEEKLY_HOURS,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    data = entry.data
    async_add_entities(
        [
            TempoWorklogSensor(
                hass,
                token=data[CONF_API_TOKEN],
                base_url=data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                min_hours=float(data.get(CONF_MIN_HOURS, DEFAULT_MIN_HOURS)),
                weekly_hours=float(data.get(CONF_WEEKLY_HOURS, DEFAULT_WEEKLY_HOURS)),
                account_id=data.get(CONF_ACCOUNT_ID, ""),
                entry_id=entry.entry_id,
            )
        ],
        update_before_add=True,
    )


def _count_required_hours(from_date: date, to_date: date, weekly_hours: float = 40.0) -> float:
    """Count Mon-Fri days in range and multiply by 8h."""
    count = 0
    d = from_date
    while d <= to_date:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return round(count * (weekly_hours / 5), 1)


class TempoWorklogSensor(SensorEntity):

    def __init__(self, hass, token, base_url, min_hours, weekly_hours, account_id, entry_id):
        self._hass = hass
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._min_hours = min_hours
        self._weekly_hours = weekly_hours
        self._account_id = account_id
        self._entry_id = entry_id
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        return DEFAULT_NAME

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._entry_id}_today"

    @property
    def native_value(self):
        return self._state

    @property
    def native_unit_of_measurement(self):
        return "h"

    @property
    def icon(self):
        return "mdi:briefcase-check" if self._attributes.get("today_logged") else "mdi:briefcase-clock"

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update(self):
        today = dt_util.now().date()
        month_start = today.replace(day=1)
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        fetch_from = today - timedelta(days=60)
        fetch_to = max(today, friday)

        session = async_get_clientsession(self._hass)
        headers = {"Authorization": f"Bearer {self._token}"}

        try:
            # Main request: month start → end of week (covers week dots + monthly stats + issues)
            results = await self._fetch_worklogs(session, headers, month_start, fetch_to)
            # Extra request for streak: up to 30 days before month start
            if month_start > fetch_from:
                prev_results = await self._fetch_worklogs(session, headers, fetch_from, month_start - timedelta(days=1))
                results = prev_results + results
        except Exception as exc:
            _LOGGER.warning("Tempo API request failed: %s", exc)
            return

        # Aggregate
        day_seconds = {}
        issue_data = {}

        for wl in results:
            # Client-side filter: skip entries that don't belong to configured user
            if self._account_id:
                author_id = wl.get("author", {}).get("accountId", "")
                if author_id != self._account_id:
                    continue

            d = wl.get("startDate")
            secs = float(wl.get("timeSpentSeconds", 0))
            if d:
                day_seconds[d] = day_seconds.get(d, 0.0) + secs

            if d and d >= month_start.isoformat():
                issue = wl.get("issue", {})
                key = issue.get("key", "")
                if key:
                    if key not in issue_data:
                        issue_data[key] = {"key": key, "seconds": 0.0, "description": ""}
                    issue_data[key]["seconds"] += secs
                    desc = wl.get("description", "")
                    if len(desc) > len(issue_data[key]["description"]):
                        issue_data[key]["description"] = desc

        # Today
        today_hours = round(day_seconds.get(today.isoformat(), 0.0) / 3600, 1)
        today_logged = today_hours >= self._min_hours

        # Week dots
        week_days = []
        for i in range(5):
            d = monday + timedelta(days=i)
            h = round(day_seconds.get(d.isoformat(), 0.0) / 3600, 1)
            week_days.append({
                "date": d.isoformat(),
                "day_name": d.strftime("%a"),
                "hours": h,
                "logged": h >= self._min_hours,
                "is_today": d == today,
                "is_future": d > today,
            })

        days_logged_week = sum(1 for d in week_days if d["logged"] and not d["is_future"])

        # Month
        month_seconds = sum(
            s for ds, s in day_seconds.items()
            if month_start.isoformat() <= ds <= today.isoformat()
        )
        month_hours = round(month_seconds / 3600, 1)
        month_required = _count_required_hours(month_start, today, self._weekly_hours)

        # Streak — consecutive working days going back
        streak = 0
        check = today
        if not today_logged and today.weekday() < 5:
            check = today - timedelta(days=1)
        while True:
            if check.weekday() >= 5:
                check -= timedelta(days=1)
                continue
            h = day_seconds.get(check.isoformat(), 0.0) / 3600
            if h >= self._min_hours:
                streak += 1
                check -= timedelta(days=1)
            else:
                break
            if (today - check).days > 62:
                break

        # Top issues
        top_issues = sorted(issue_data.values(), key=lambda x: x["seconds"], reverse=True)[:10]
        top_issues_out = [
            {
                "key": iss["key"],
                "hours": round(iss["seconds"] / 3600, 1),
                "description": iss["description"][:80] if iss["description"] else "",
            }
            for iss in top_issues
        ]

        self._state = today_hours
        self._attributes = {
            "today_logged": today_logged,
            "min_hours": self._min_hours,
            "week_days": week_days,
            "week_start_date": monday.isoformat(),
            "days_logged_this_week": days_logged_week,
            "month_hours": month_hours,
            "month_required_hours": month_required,
            "weekly_hours": self._weekly_hours,
            "streak": streak,
            "month_issues": top_issues_out,
            "friendly_name": self.name,
        }

    async def _fetch_worklogs(self, session, headers, from_date, to_date):
        """Fetch all worklogs using Tempo's metadata.next pagination."""
        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "limit": 1000,
        }

        results = []
        # Use user-specific endpoint when account_id is set — /worklogs doesn't support user filtering via params
        if self._account_id:
            url = f"{self._base_url}/worklogs/user/{self._account_id}"
        else:
            url = f"{self._base_url}/worklogs"

        while url:
            async with session.get(
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Tempo API returned HTTP %s", resp.status)
                    break
                data = await resp.json()

            batch = data.get("results", [])
            results.extend(batch)

            # Use Tempo's own next-page URL — most reliable pagination
            next_url = data.get("metadata", {}).get("next")
            if next_url:
                url = next_url
                params = {}  # next URL already contains all query params
            else:
                break

        return results
