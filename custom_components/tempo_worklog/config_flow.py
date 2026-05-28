"""Config flow for Tempo Worklog integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_TOKEN,
    CONF_BASE_URL,
    CONF_MIN_HOURS,
    DEFAULT_BASE_URL,
    DEFAULT_MIN_HOURS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_token(hass: HomeAssistant, token: str, base_url: str) -> str | None:
    """
    Try a lightweight Tempo API call to check if the token is valid.
    Returns None on success, or an error key string on failure.
    """
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base_url.rstrip('/')}/worklogs"

    try:
        async with session.get(
            url,
            headers=headers,
            params={"limit": 1},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 401:
                return "invalid_token"
            if resp.status == 403:
                return "invalid_token"
            if resp.status not in (200, 204):
                return "cannot_connect"
            return None
    except aiohttp.ClientConnectorError:
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        return "unknown"


class TempoWorklogConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the setup form and validate input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL).strip()
            min_hours = float(user_input.get(CONF_MIN_HOURS, DEFAULT_MIN_HOURS))

            error = await _validate_token(self.hass, token, base_url)
            if error:
                errors["base"] = error
            else:
                # Prevent duplicate entries
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Tempo Worklog",
                    data={
                        CONF_API_TOKEN: token,
                        CONF_BASE_URL: base_url,
                        CONF_MIN_HOURS: min_hours,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): str,
                    vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
                    vol.Optional(CONF_MIN_HOURS, default=DEFAULT_MIN_HOURS): vol.Coerce(float),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow (for re-configuring after setup)."""
        return TempoWorklogOptionsFlow(config_entry)


class TempoWorklogOptionsFlow(config_entries.OptionsFlow):
    """Allow the user to reconfigure token / URL / min_hours after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show the options form."""
        errors: dict[str, str] = {}
        current = self._config_entry.data

        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            base_url = user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL).strip()
            min_hours = float(user_input.get(CONF_MIN_HOURS, DEFAULT_MIN_HOURS))

            error = await _validate_token(self.hass, token, base_url)
            if error:
                errors["base"] = error
            else:
                # Update the config entry data in place
                self.hass.config_entries.async_update_entry(
                    self._config_entry,
                    data={
                        CONF_API_TOKEN: token,
                        CONF_BASE_URL: base_url,
                        CONF_MIN_HOURS: min_hours,
                    },
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_TOKEN,
                        default=current.get(CONF_API_TOKEN, ""),
                    ): str,
                    vol.Optional(
                        CONF_BASE_URL,
                        default=current.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                    ): str,
                    vol.Optional(
                        CONF_MIN_HOURS,
                        default=current.get(CONF_MIN_HOURS, DEFAULT_MIN_HOURS),
                    ): vol.Coerce(float),
                }
            ),
            errors=errors,
        )
