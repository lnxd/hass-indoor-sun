"""Indoor Sun Brightness & RGB sensors."""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
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
    """Set up Indoor Sun sensor entities from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Configuration entry containing connection details.
        async_add_entities: Callback to add entities to Home Assistant.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BrightnessSensor(coordinator, entry),
        RGBSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class IndoorSunSensorBase(CoordinatorEntity, SensorEntity):  # type: ignore[misc]
    """Base class for Indoor Sun sensors.

    Provides common functionality for all Indoor Sun sensor entities,
    including device information and availability checking.
    """

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor base class.

        Args:
            coordinator: The data coordinator managing updates.
            entry: Configuration entry containing device information.
        """
        super().__init__(coordinator)
        self._entry = entry
        data = {**entry.data, **entry.options}

        source_type = data.get("source_type", "frigate")
        if source_type == "frigate":
            camera_name = data.get("camera_name", data.get("camera", "unknown"))
            device_name = f"Indoor Sun {camera_name}"
        else:
            device_name = "Indoor Sun Snapshot"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": device_name,
            "manufacturer": "Indoor Sun",
            "model": f"{source_type.title()} Camera Analyzer",
            "sw_version": "1.0.0",
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Returns:
            bool: True if coordinator has successfully updated.
        """
        return bool(self.coordinator.last_update_success)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes common to all sensors.

        Returns:
            Dict[str, Any]: Dictionary containing camera information and processing status.
        """
        if self.coordinator.data is None:
            return {}

        data = {**self._entry.data, **self._entry.options}
        attrs = {
            "camera": data["camera"],
            "source_type": self.coordinator.data.get("source_type", "frigate"),
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

        return attrs


class BrightnessSensor(IndoorSunSensorBase):
    """Sensor for brightness percentage.

    Reports the calculated brightness as a percentage value with
    percentage device class for proper display in Home Assistant.
    """

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the brightness sensor.

        Args:
            coordinator: The data coordinator managing updates.
            entry: Configuration entry containing device information.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_brightness"
        self._attr_name = "Sun Brightness"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = "percentage"
        self._attr_state_class = "measurement"
        self._attr_icon = "mdi:brightness-percent"

    @property
    def native_value(self) -> Optional[float]:
        """Return the brightness percentage.

        Returns:
            Optional[float]: The brightness percentage (0-100), or None if
                           data is not available.
        """
        if self.coordinator.data is None:
            return None
        brightness = self.coordinator.data.get("brightness")
        return float(brightness) if brightness is not None else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dict[str, Any]: Dictionary containing RGB values and processing information.
        """
        attrs = super().extra_state_attributes

        if self.coordinator.data is not None:
            attrs.update(
                {
                    "r": self.coordinator.data.get("r"),
                    "g": self.coordinator.data.get("g"),
                    "b": self.coordinator.data.get("b"),
                    "rgb_string": self.coordinator.data.get("rgb_string"),
                }
            )

        return attrs


class RGBSensor(IndoorSunSensorBase):
    """Sensor for RGB values.

    Reports the average RGB values of the analyzed camera image
    as a formatted string.
    """

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the RGB sensor.

        Args:
            coordinator: The data coordinator managing updates.
            entry: Configuration entry containing device information.
        """
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rgb"
        self._attr_name = "Sun RGB"
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_icon = "mdi:palette"

    @property
    def native_value(self) -> Optional[str]:
        """Return the RGB values as a formatted string.

        Returns:
            Optional[str]: The RGB values as "R, G, B" format, or None if
                          data is not available.
        """
        if self.coordinator.data is None:
            return None
        rgb_string = self.coordinator.data.get("rgb_string")
        return rgb_string if rgb_string is not None else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes.

        Returns:
            Dict[str, Any]: Dictionary containing individual RGB values and brightness.
        """
        attrs = super().extra_state_attributes

        if self.coordinator.data is not None:
            attrs.update(
                {
                    "brightness": self.coordinator.data.get("brightness"),
                    "r": self.coordinator.data.get("r"),
                    "g": self.coordinator.data.get("g"),
                    "b": self.coordinator.data.get("b"),
                }
            )

        return attrs
