"""UI config flow for Indoor Sun."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Dict, Optional

import async_timeout
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from PIL import Image

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_SOURCE_SCHEMA = vol.Schema(
    {vol.Required("source_type", default="frigate"): vol.In(["frigate", "snapshot"])}
)

STEP_FRIGATE_SCHEMA = vol.Schema(
    {
        vol.Required("protocol", default="http"): vol.In(["http", "https"]),
        vol.Required("host"): str,
        vol.Optional("port"): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required("camera_name"): str,
    }
)

STEP_SNAPSHOT_SCHEMA = vol.Schema(
    {
        vol.Required("snapshot_url"): str,
    }
)

STEP_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Optional("scan_interval", default=60): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=3600)
        ),
        vol.Optional("enable_image_entity", default=False): bool,
    }
)

STEP_IMAGE_PROCESSING_SCHEMA = vol.Schema(
    {
        vol.Optional("enable_cropping", default=False): bool,
        vol.Optional("top_left_x"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("top_left_y"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("bottom_right_x"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("bottom_right_y"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("enable_brightness_adjustment", default=False): bool,
        vol.Optional("min_brightness", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional("max_brightness", default=100): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional("enable_color_adjustment", default=False): bool,
        vol.Optional("min_color_r", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("min_color_g", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("min_color_b", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("max_color_r", default=255): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("max_color_g", default=255): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
        vol.Optional("max_color_b", default=255): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
    }
)


class IndoorSunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc, call-arg]
    """Handle the config flow for Indoor Sun integration.

    Provides a user interface for configuring the Indoor Sun integration,
    with multi-step configuration for better user experience.
    """

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.config_data: Dict[str, Any] = {}
        self.test_image_data: Optional[bytes] = None
        self.test_image_url: Optional[str] = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - source selection.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or proceed to next step.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self.config_data.update(user_input)

            if user_input["source_type"] == "frigate":
                return await self.async_step_frigate()
            else:
                return await self.async_step_snapshot()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SOURCE_SCHEMA,
            errors=errors,
        )

    async def async_step_frigate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Frigate configuration.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or proceed to next step.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            if "port" not in user_input or user_input["port"] is None:
                user_input["port"] = 443 if user_input["protocol"] == "https" else 5000

            base_url = (
                f"{user_input['protocol']}://{user_input['host']}:{user_input['port']}"
            )

            self.config_data.update(user_input)
            self.config_data["base_url"] = base_url
            self.config_data["camera"] = user_input["camera_name"]

            self.test_image_url = (
                f"{base_url}/api/{user_input['camera_name']}/latest.jpg"
            )

            return await self.async_step_test_connection()

        schema_dict = {
            vol.Required(
                "protocol", default=self.config_data.get("protocol", "http")
            ): vol.In(["http", "https"]),
            vol.Required("host", default=self.config_data.get("host", "")): str,
            vol.Required(
                "camera_name", default=self.config_data.get("camera_name", "")
            ): str,
        }

        protocol = self.config_data.get("protocol", "http")
        default_port = 443 if protocol == "https" else 5000
        schema_dict[vol.Optional("port", default=default_port)] = vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        )

        dynamic_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="frigate",
            data_schema=dynamic_schema,
            errors=errors,
        )

    async def async_step_snapshot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle snapshot URL configuration.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or proceed to next step.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            snapshot_url = user_input["snapshot_url"].strip()

            if not snapshot_url.startswith(("http://", "https://")):
                errors["snapshot_url"] = "url_invalid_protocol"
            else:
                self.config_data.update(user_input)
                self.config_data["base_url"] = snapshot_url
                self.config_data["camera"] = "snapshot"
                self.test_image_url = snapshot_url

                return await self.async_step_test_connection()

        return self.async_show_form(
            step_id="snapshot",
            data_schema=STEP_SNAPSHOT_SCHEMA,
            errors=errors,
        )

    async def async_step_test_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle connection testing.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or proceed to next step.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            if "test_connection" in user_input:
                try:
                    session = async_get_clientsession(self.hass)

                    async with async_timeout.timeout(10):
                        async with session.get(self.test_image_url) as response:
                            if response.status == 200:
                                self.test_image_data = await response.read()

                                try:
                                    if self.test_image_data:
                                        with Image.open(BytesIO(self.test_image_data)):
                                            pass
                                except Exception:
                                    errors["base"] = "invalid_image_format"
                                    self.test_image_data = None
                            else:
                                errors["base"] = "connection_failed"

                except Exception as err:
                    _LOGGER.error("Connection test failed: %s", err)
                    errors["base"] = "connection_error"

            elif "proceed_anyway" in user_input:
                pass

            elif "proceed" in user_input and self.test_image_data:
                return await self.async_step_settings()

            elif "retest" in user_input:
                errors.pop("base", None)
                self.test_image_data = None

            else:
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="test_connection",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "url": self.test_image_url,
                "status": "Success" if self.test_image_data else "Not tested",
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle general settings configuration.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or proceed to next step.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_image_processing()

        return self.async_show_form(
            step_id="settings",
            data_schema=STEP_SETTINGS_SCHEMA,
            errors=errors,
        )

    async def async_step_image_processing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle image processing configuration.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or create the final entry.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("enable_cropping", False):
                crop_coords = [
                    "top_left_x",
                    "top_left_y",
                    "bottom_right_x",
                    "bottom_right_y",
                ]
                if not all(
                    coord in user_input and user_input[coord] is not None
                    for coord in crop_coords
                ):
                    errors["base"] = "crop_coordinates_incomplete"
                elif (
                    user_input["top_left_x"] >= user_input["bottom_right_x"]
                    or user_input["top_left_y"] >= user_input["bottom_right_y"]
                ):
                    errors["base"] = "crop_coordinates_invalid"

            if user_input.get("enable_brightness_adjustment", False):
                if user_input["min_brightness"] >= user_input["max_brightness"]:
                    errors["base"] = "brightness_range_invalid"

            if user_input.get("enable_color_adjustment", False):
                color_pairs = [
                    ("min_color_r", "max_color_r"),
                    ("min_color_g", "max_color_g"),
                    ("min_color_b", "max_color_b"),
                ]
                for min_key, max_key in color_pairs:
                    if user_input[min_key] >= user_input[max_key]:
                        errors["base"] = "color_range_invalid"
                        break

            if not errors:
                self.config_data.update(user_input)

                final_config = self._prepare_final_config()

                title = self._get_entry_title()
                return self.async_create_entry(title=title, data=final_config)

        return self.async_show_form(
            step_id="image_processing",
            data_schema=STEP_IMAGE_PROCESSING_SCHEMA,
            errors=errors,
        )

    def _prepare_final_config(self) -> Dict[str, Any]:
        """Prepare the final configuration dictionary.

        Returns:
            Dict[str, Any]: Clean configuration dictionary for the entry.
        """
        config = {
            "source_type": self.config_data["source_type"],
            "base_url": self.config_data["base_url"],
            "camera": self.config_data["camera"],
            "scan_interval": self.config_data.get("scan_interval", 60),
            "enable_image_entity": self.config_data.get("enable_image_entity", False),
        }

        if self.config_data.get("enable_cropping", False):
            config.update(
                {
                    "top_left_x": self.config_data["top_left_x"],
                    "top_left_y": self.config_data["top_left_y"],
                    "bottom_right_x": self.config_data["bottom_right_x"],
                    "bottom_right_y": self.config_data["bottom_right_y"],
                }
            )

        if self.config_data.get("enable_brightness_adjustment", False):
            config.update(
                {
                    "min_brightness": self.config_data["min_brightness"],
                    "max_brightness": self.config_data["max_brightness"],
                }
            )

        if self.config_data.get("enable_color_adjustment", False):
            config.update(
                {
                    "min_color_r": self.config_data["min_color_r"],
                    "min_color_g": self.config_data["min_color_g"],
                    "min_color_b": self.config_data["min_color_b"],
                    "max_color_r": self.config_data["max_color_r"],
                    "max_color_g": self.config_data["max_color_g"],
                    "max_color_b": self.config_data["max_color_b"],
                }
            )

        if self.config_data["source_type"] == "frigate":
            config.update(
                {
                    "protocol": self.config_data["protocol"],
                    "host": self.config_data["host"],
                    "port": self.config_data["port"],
                    "camera_name": self.config_data["camera_name"],
                }
            )
        else:
            config["snapshot_url"] = self.config_data["snapshot_url"]

        return config

    def _get_entry_title(self) -> str:
        """Get an appropriate title for the config entry.

        Returns:
            str: Human-readable title for the integration entry.
        """
        if self.config_data["source_type"] == "frigate":
            return f"Indoor Sun - {self.config_data['camera_name']}"
        else:
            return "Indoor Sun - Snapshot"


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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options configuration step.

        Args:
            user_input: Optional dictionary containing user input from the form.

        Returns:
            FlowResult: Either a form to display or a successful entry update.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            if (
                "min_brightness" in user_input
                and "max_brightness" in user_input
                and user_input["min_brightness"] >= user_input["max_brightness"]
            ):
                errors["base"] = "brightness_range_invalid"

            for ch in ("r", "g", "b"):
                min_key, max_key = f"min_color_{ch}", f"max_color_{ch}"
                if min_key in user_input and max_key in user_input:
                    if user_input[min_key] >= user_input[max_key]:
                        errors["base"] = "color_range_invalid"
                        break

            if any(
                coord in user_input
                for coord in [
                    "top_left_x",
                    "top_left_y",
                    "bottom_right_x",
                    "bottom_right_y",
                ]
            ):
                required = [
                    "top_left_x",
                    "top_left_y",
                    "bottom_right_x",
                    "bottom_right_y",
                ]
                if not all(
                    coord in user_input and user_input[coord] is not None
                    for coord in required
                ):
                    errors["base"] = "crop_coordinates_incomplete"
                elif (
                    user_input["top_left_x"] >= user_input["bottom_right_x"]
                    or user_input["top_left_y"] >= user_input["bottom_right_y"]
                ):
                    errors["base"] = "crop_coordinates_invalid"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        cur = {**self.config_entry.data, **self.config_entry.options}

        schema_dict = {
            vol.Optional(
                "scan_interval", default=cur.get("scan_interval", 60)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
            vol.Optional(
                "enable_image_entity", default=cur.get("enable_image_entity", False)
            ): bool,
            vol.Optional("top_left_x", default=cur.get("top_left_x")): vol.Any(
                int, None
            ),
            vol.Optional("top_left_y", default=cur.get("top_left_y")): vol.Any(
                int, None
            ),
            vol.Optional("bottom_right_x", default=cur.get("bottom_right_x")): vol.Any(
                int, None
            ),
            vol.Optional("bottom_right_y", default=cur.get("bottom_right_y")): vol.Any(
                int, None
            ),
        }

        if any(key in cur for key in ["min_brightness", "max_brightness"]):
            schema_dict.update(
                {
                    vol.Optional(
                        "min_brightness", default=cur.get("min_brightness", 0)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                    vol.Optional(
                        "max_brightness", default=cur.get("max_brightness", 100)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
                }
            )

        if any(key in cur for key in ["min_color_r", "max_color_r"]):
            schema_dict.update(
                {
                    vol.Optional(
                        "min_color_r", default=cur.get("min_color_r", 0)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                    vol.Optional(
                        "min_color_g", default=cur.get("min_color_g", 0)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                    vol.Optional(
                        "min_color_b", default=cur.get("min_color_b", 0)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                    vol.Optional(
                        "max_color_r", default=cur.get("max_color_r", 255)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                    vol.Optional(
                        "max_color_g", default=cur.get("max_color_g", 255)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                    vol.Optional(
                        "max_color_b", default=cur.get("max_color_b", 255)
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                }
            )

        schema = vol.Schema(schema_dict)

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
