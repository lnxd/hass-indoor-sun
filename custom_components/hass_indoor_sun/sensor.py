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
    """Set up Indoor Sun sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        BrightnessSensor(coordinator, entry),
        RGBSensor(coordinator, entry),
    ]
    
    async_add_entities(entities)


class IndoorSunSensorBase(CoordinatorEntity, SensorEntity):  # type: ignore[misc]
    """Base class for Indoor Sun sensors."""

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        data = {**entry.data, **entry.options}
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Indoor Sun {data['camera']}",
            "manufacturer": "Indoor Sun",
            "model": "Frigate Camera Analyzer",
            "sw_version": "0.1.1",
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success)


class BrightnessSensor(IndoorSunSensorBase):
    """Sensor for brightness percentage."""

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the brightness sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_brightness"
        self._attr_name = "Sun Brightness"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:brightness-percent"

    @property
    def native_value(self) -> Optional[float]:
        """Return the brightness percentage."""
        if self.coordinator.data is None:
            return None
        brightness = self.coordinator.data.get("brightness")
        return float(brightness) if brightness is not None else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        
        data = {**self._entry.data, **self._entry.options}
        return {
            "camera": data["camera"],
            "base_url": data["base_url"],
            "r": self.coordinator.data.get("r"),
            "g": self.coordinator.data.get("g"),
            "b": self.coordinator.data.get("b"),
        }


class RGBSensor(IndoorSunSensorBase):
    """Sensor for RGB values."""

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the RGB sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rgb"
        self._attr_name = "Sun RGB"
        self._attr_icon = "mdi:palette"

    @property
    def native_value(self) -> Optional[str]:
        """Return the RGB string."""
        if self.coordinator.data is None:
            return None
        rgb_string = self.coordinator.data.get("rgb_string")
        return str(rgb_string) if rgb_string is not None else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        
        data = {**self._entry.data, **self._entry.options}
        return {
            "camera": data["camera"],
            "base_url": data["base_url"],
            "r": self.coordinator.data.get("r"),
            "g": self.coordinator.data.get("g"),
            "b": self.coordinator.data.get("b"),
            "brightness": self.coordinator.data.get("brightness"),
        } 