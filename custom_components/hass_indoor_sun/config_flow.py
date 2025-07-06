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
        vol.Optional("enable_image_entity", default=False): bool,
        vol.Optional("top_left_x"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("top_left_y"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("bottom_right_x"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("bottom_right_y"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)


class IndoorSunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc, call-arg]
    """Handle the config flow for Indoor Sun integration.
    
    Provides a user interface for configuring the Indoor Sun integration,
    including Frigate API connection details and optional image cropping.
    """

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial configuration step.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or a successful entry creation.
        """
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Validate crop coordinates if any are provided
            if any(coord in user_input for coord in ["top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"]):
                required_coords = ["top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"]
                if not all(coord in user_input and user_input[coord] is not None for coord in required_coords):
                    errors["base"] = "crop_coordinates_incomplete"
                elif (user_input["top_left_x"] >= user_input["bottom_right_x"] or 
                      user_input["top_left_y"] >= user_input["bottom_right_y"]):
                    errors["base"] = "crop_coordinates_invalid"
            
            if not errors:
                return self.async_create_entry(
                    title=user_input["camera"], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class IndoorSunOptionsFlow(config_entries.OptionsFlow):  # type: ignore[misc]
    """Handle options flow for Indoor Sun integration.
    
    Allows users to modify configuration settings after the integration
    has been initially set up.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow.

        Args:
            config_entry: The configuration entry to create options for.
        """
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the options configuration step.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or a successful entry update.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate crop coordinates if any are provided
            if any(coord in user_input for coord in ["top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"]):
                required = ["top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"]
                if not all(coord in user_input and user_input[coord] is not None for coord in required):
                    errors["base"] = "crop_coordinates_incomplete"
                elif (user_input["top_left_x"] >= user_input["bottom_right_x"] or
                      user_input["top_left_y"] >= user_input["bottom_right_y"]):
                    errors["base"] = "crop_coordinates_invalid"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Pre-fill form with current configuration values
        cur = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required("base_url", default=cur["base_url"]): str,
                vol.Required("camera", default=cur["camera"]): str,
                vol.Optional("scan_interval", default=cur.get("scan_interval", 60)): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=3600)
                ),
                vol.Optional("enable_image_entity", default=cur.get("enable_image_entity", False)): bool,
                vol.Optional("top_left_x", default=cur.get("top_left_x")): vol.Any(int, None),
                vol.Optional("top_left_y", default=cur.get("top_left_y")): vol.Any(int, None),
                vol.Optional("bottom_right_x", default=cur.get("bottom_right_x")): vol.Any(int, None),
                vol.Optional("bottom_right_y", default=cur.get("bottom_right_y")): vol.Any(int, None),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors) 