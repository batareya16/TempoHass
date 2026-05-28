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
    CONF_MIN_HOURS,
    DEFAULT_BASE_URL,
    DEFAULT_MIN_HOURS,
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
                entry_id=entry.entry_id,
            )
        ],
        update_before_add=True,
    )


def _count_required_hours(from_date: date, to_date: date) -> float:
    """Count Mon-Fri days in range and multiply by 8h."""
    count = 0
    d = from_date
    while d <= to_date:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return float(count * 8)


class TempoWorklogSensor(SensorEntity):

    def __init__(self, hass, token, base_url, min_hours, entry_id):
        self._hass = hass
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._min_hours = min_hours
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
            results = await self._fetch_all_worklogs(session, headers, fetch_from, fetch_to)
        except Exception as exc:
            _LOGGER.error("Tempo API request failed: %s", exc)
            return

        # Aggregate
        day_seconds = {}
        issue_data = {}

        for wl in results:
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
        month_required = _count_required_hours(month_start, today)

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
            "streak": streak,
            "month_issues": top_issues_out,
            "friendly_name": self.name,
        }

    async def _fetch_all_worklogs(self, session, headers, from_date, to_date):
        results = []
        offset = 0
        limit = 1000
        while True:
            params = {
                "from": from_date.isoformat(),
                "to": to_date.isoformat(),
                "limit": limit,
                "offset": offset,
            }
            async with session.get(
                f"{self._base_url}/worklogs",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Tempo API returned HTTP %s", resp.status)
                    break
                data = await resp.json()
            batch = data.get("results", [])
            results.extend(batch)
            metadata = data.get("metadata", {})
            total = metadata.get("count", len(results))
            offset += len(batch)
            if offset >= total or not batch:
                break
        return results
