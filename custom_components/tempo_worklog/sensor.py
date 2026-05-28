"""Tempo Worklog sensor — tracks logged hours per day (Mon–Fri) via Tempo Cloud API v4."""
import logging
from datetime import date, timedelta

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
    """Set up sensor from a config entry."""
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


class TempoWorklogSensor(SensorEntity):
    """Sensor that shows today's logged hours and weekly status (Mon–Fri)."""

    def __init__(
        self,
        hass: HomeAssistant,
        token: str,
        base_url: str,
        min_hours: float,
        entry_id: str,
    ):
        self._hass = hass
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._min_hours = min_hours
        self._entry_id = entry_id
        self._state = None
        self._attributes = {}

    # ── HA properties ──────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return DEFAULT_NAME

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_today"

    @property
    def native_value(self):
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        return "h"

    @property
    def icon(self) -> str:
        if self._attributes.get("today_logged"):
            return "mdi:briefcase-check"
        return "mdi:briefcase-clock"

    @property
    def extra_state_attributes(self) -> dict:
        return self._attributes

    # ── Fetching ───────────────────────────────────────────────────────────────

    async def async_update(self) -> None:
        """Fetch worklogs from Tempo API and compute daily totals."""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)

        session = async_get_clientsession(self._hass)
        headers = {"Authorization": f"Bearer {self._token}"}

        params = {
            "from": monday.isoformat(),
            "to": friday.isoformat(),
            "limit": 1000,
        }

        try:
            async with session.get(
                f"{self._base_url}/worklogs",
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Tempo API returned %s", resp.status)
                    return
                data = await resp.json()
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Tempo API request failed: %s", exc)
            return

        # Sum seconds per date string
        day_seconds: dict[str, float] = {}
        for wl in data.get("results", []):
            d = wl.get("startDate")
            if d:
                day_seconds[d] = day_seconds.get(d, 0.0) + wl.get("timeSpentSeconds", 0)

        # Build week_days list Mon–Fri
        week_days = []
        for i in range(5):
            d = monday + timedelta(days=i)
            seconds = day_seconds.get(d.isoformat(), 0.0)
            hours = round(seconds / 3600, 1)
            is_today = d == today
            is_future = d > today
            week_days.append(
                {
                    "date": d.isoformat(),
                    "day_name": d.strftime("%a"),
                    "hours": hours,
                    "logged": hours >= self._min_hours,
                    "is_today": is_today,
                    "is_future": is_future,
                }
            )

        today_hours = day_seconds.get(today.isoformat(), 0.0) / 3600
        today_logged = today_hours >= self._min_hours

        # Days logged so far (skip future days from count)
        days_logged = sum(
            1 for d in week_days if d["logged"] and not d["is_future"]
        )

        self._state = round(today_hours, 1)
        self._attributes = {
            "week_days": week_days,
            "min_hours": self._min_hours,
            "week_start_date": monday.isoformat(),
            "today_logged": today_logged,
            "days_logged_this_week": days_logged,
            "friendly_name": self._name,
        }
