"""Indoor Sun Image platform.

Provides image entities for displaying processed camera frames from the Indoor
Sun integration. The image entity shows the current or cropped image from the
camera source being analyzed for brightness and RGB values.

The image entity automatically works with the new Home Assistant Image API
and provides additional state attributes with camera information,
processing status, and configuration details.
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, IndoorSunCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Indoor Sun image entities from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Configuration entry containing connection details.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        IndoorSunImageEntity(coordinator, entry),
    ]

    async_add_entities(entities)


class IndoorSunImageEntity(CoordinatorEntity, ImageEntity):  # type: ignore[misc]
    """Image entity for displaying the processed camera frame.

    Shows the current or cropped image from the camera source that is
    being analyzed for brightness and RGB values.
    """

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the image entity.

        Args:
            coordinator: The data coordinator managing updates.
            entry: Configuration entry containing device information.
        """
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self)
        
        self._entry = entry
        data = {**entry.data, **entry.options}

        source_type = data.get("source_type", "frigate")
        if source_type == "frigate":
            camera_name = data.get("camera_name", data.get("camera", "unknown"))
            device_name = f"Indoor Sun {camera_name}"
        else:
            device_name = "Indoor Sun Snapshot"

        self._attr_unique_id = f"{entry.entry_id}_image"
        self._attr_name = "Sun Reference Image"
        self._attr_content_type = "image/jpeg"
        self._attr_exclude_from_recorder = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": device_name,
            "manufacturer": "Indoor Sun",
            "model": f"{source_type.title()} Camera Analyzer",
            "sw_version": "0.2.0",
        }
        self._attr_entity_registry_enabled_default = True

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Returns:
            bool: True if coordinator has successfully updated and image data
                exists.
        """
        return bool(
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "image_data" in self.coordinator.data
        )

    async def async_get_image(self) -> Optional[bytes]:
        """Return the current image data using the new Image API.

        Returns:
            Optional[bytes]: The JPEG image data, or None if not available.
        """
        if self.coordinator.data is None:
            return None

        image_data = self.coordinator.data.get("image_data")
        if image_data is None:
            return None

        import base64

        try:
            return base64.b64decode(image_data)
        except Exception as err:
            _LOGGER.error("Failed to decode base64 image data: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dict[str, Any]: Dictionary containing camera information,
                           processing status, and configuration details.
        """
        if self.coordinator.data is None:
            return {}

        data = {**self._entry.data, **self._entry.options}
        attrs = {
            "camera": data["camera"],
            "source_type": self.coordinator.source_type,
            "image_url": self.coordinator.image_url,
            "scan_interval": data.get("scan_interval", 60),
        }

        if "cropped" in self.coordinator.data:
            attrs["cropped"] = self.coordinator.data["cropped"]
        if "brightness_adjusted" in self.coordinator.data:
            attrs["brightness_adjusted"] = self.coordinator.data["brightness_adjusted"]
        if "color_adjusted" in self.coordinator.data:
            attrs["color_adjusted"] = self.coordinator.data["color_adjusted"]

        if self.coordinator.crop_coordinates:
            attrs["crop_coordinates"] = {
                "top_left_x": self.coordinator.crop_coordinates[0],
                "top_left_y": self.coordinator.crop_coordinates[1],
                "bottom_right_x": self.coordinator.crop_coordinates[2],
                "bottom_right_y": self.coordinator.crop_coordinates[3],
            }

        if self.coordinator.brightness_adjustment_enabled:
            attrs["brightness_range"] = {
                "min": self.coordinator.min_brightness,
                "max": self.coordinator.max_brightness,
            }

        if self.coordinator.color_adjustment_enabled:
            attrs["color_range"] = {
                "min_r": self.coordinator.min_color[0],
                "min_g": self.coordinator.min_color[1],
                "min_b": self.coordinator.min_color[2],
                "max_r": self.coordinator.max_color[0],
                "max_g": self.coordinator.max_color[1],
                "max_b": self.coordinator.max_color[2],
            }

        if self.coordinator.data is not None:
            attrs.update(
                {
                    "current_brightness": self.coordinator.data.get("brightness"),
                    "current_r": self.coordinator.data.get("r"),
                    "current_g": self.coordinator.data.get("g"),
                    "current_b": self.coordinator.data.get("b"),
                    "current_rgb_string": self.coordinator.data.get("rgb_string"),
                }
            )

        return attrs
