"""Indoor Sun Brightness & RGB Component for Home Assistant."""
import base64
import logging
from datetime import timedelta
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import async_timeout
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from PIL import Image

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hass_indoor_sun"
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Indoor Sun from a config entry."""
    coordinator = IndoorSunCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    data = {**entry.data, **entry.options}
    platforms = ["sensor"]
    if data.get("enable_image_entity", False):
        platforms.append("image")

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = {**entry.data, **entry.options}
    platforms = ["sensor"]
    if data.get("enable_image_entity", False):
        platforms.append("image")
    
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class IndoorSunCoordinator(DataUpdateCoordinator[Dict[str, Any]]):  # type: ignore[misc]
    """Coordinator for Indoor Sun component."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        data = {**entry.data, **entry.options}
        self.base_url = data["base_url"]
        self.camera = data["camera"]
        self.scan_interval = data.get("scan_interval", 60)
        self.enable_image_entity = data.get("enable_image_entity", False)
        
        self.crop_coordinates: Optional[Tuple[int, int, int, int]] = None
        if all(coord in data for coord in ["top_left_x", "top_left_y", "bottom_right_x", "bottom_right_y"]):
            self.crop_coordinates = (
                data["top_left_x"],
                data["top_left_y"],
                data["bottom_right_x"],
                data["bottom_right_y"],
            )
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Frigate camera."""
        try:
            async with async_timeout.timeout(10):
                return await self._fetch_and_process_frame()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Frigate: {err}") from err

    async def _fetch_and_process_frame(self) -> Dict[str, Any]:
        """Fetch JPEG frame from Frigate and process it."""
        session = async_get_clientsession(self.hass)
        url = f"{self.base_url}/api/{self.camera}/latest.jpg"
        
        async with session.get(url) as response:
            if response.status != 200:
                raise UpdateFailed(f"Failed to fetch frame: HTTP {response.status}")
            
            image_data = await response.read()
            
        result: Dict[str, Any] = await self.hass.async_add_executor_job(
            self._process_image, image_data
        )
        return result

    def _process_image(self, image_data: bytes) -> Dict[str, Any]:
        """Process the image to calculate brightness and RGB values."""
        with Image.open(BytesIO(image_data)) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            if self.crop_coordinates:
                top_left_x, top_left_y, bottom_right_x, bottom_right_y = self.crop_coordinates
                img = img.crop((top_left_x, top_left_y, bottom_right_x, bottom_right_y))
            
            pixels = list(img.getdata())
            
            total_pixels = len(pixels)
            total_r = sum(pixel[0] for pixel in pixels)
            total_g = sum(pixel[1] for pixel in pixels)
            total_b = sum(pixel[2] for pixel in pixels)
            
            avg_r = total_r / total_pixels
            avg_g = total_g / total_pixels
            avg_b = total_b / total_pixels
            
            brightness_y = 0.2126 * avg_r + 0.7152 * avg_g + 0.0722 * avg_b
            brightness_percent = (brightness_y / 255) * 100
            
            result = {
                "brightness": round(brightness_percent, 2),
                "r": round(avg_r),
                "g": round(avg_g),
                "b": round(avg_b),
                "rgb_string": f"{round(avg_r)}, {round(avg_g)}, {round(avg_b)}"
            }
            
            if self.enable_image_entity:
                img_byte_array = BytesIO()
                img.save(img_byte_array, format='JPEG', quality=85)
                img_byte_array.seek(0)
                result["image_data"] = base64.b64encode(img_byte_array.getvalue()).decode('utf-8')
            
            return result


async def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
    """Return the options flow."""
    from .config_flow import IndoorSunOptionsFlow

    return IndoorSunOptionsFlow(config_entry) 