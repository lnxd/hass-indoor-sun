"""UI config flow for Indoor Sun."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("base_url"): str,
        vol.Required("camera"): str,
        vol.Optional("scan_interval", default=60): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=3600)
        ),
    }
)


class IndoorSunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc, call-arg]
    """Handle the UI flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """First (and only) step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input["camera"], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        ) 