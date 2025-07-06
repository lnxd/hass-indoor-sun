"""Indoor Sun Image platform."""
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
    """Set up Indoor Sun image from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        IndoorSunImageEntity(coordinator, entry),
    ]
    
    async_add_entities(entities)


class IndoorSunImageEntity(CoordinatorEntity, ImageEntity):  # type: ignore[misc]
    """Image entity for the reference image."""

    def __init__(self, coordinator: IndoorSunCoordinator, entry: ConfigEntry) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator)
        self._entry = entry
        data = {**entry.data, **entry.options}
        self._attr_unique_id = f"{entry.entry_id}_image"
        self._attr_name = "Sun Reference Image"
        self._attr_content_type = "image/jpeg"
        self._attr_exclude_from_recorder = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Indoor Sun {data['camera']}",
            "manufacturer": "Indoor Sun",
            "model": "Frigate Camera Analyzer",
            "sw_version": "0.1.1",
        }
        self._attr_entity_registry_enabled_default = True

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self.coordinator.last_update_success and 
                   self.coordinator.data is not None and
                   "image_data" in self.coordinator.data)

    async def async_image(self) -> Optional[bytes]:
        """Return the image data."""
        if self.coordinator.data is None:
            return None
        
        image_data = self.coordinator.data.get("image_data")
        if image_data is None:
            return None
        
        import base64
        return base64.b64decode(image_data)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return {}
        
        data = {**self._entry.data, **self._entry.options}
        attrs = {
            "camera": data["camera"],
            "base_url": data["base_url"],
        }
        
        if self.coordinator.crop_coordinates:
            attrs["crop_coordinates"] = {
                "top_left_x": self.coordinator.crop_coordinates[0],
                "top_left_y": self.coordinator.crop_coordinates[1],
                "bottom_right_x": self.coordinator.crop_coordinates[2],
                "bottom_right_y": self.coordinator.crop_coordinates[3],
            }
        
        return attrs 