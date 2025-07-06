"""Indoor Sun Brightness & RGB Component for Home Assistant."""
import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

import aiohttp
import async_timeout
from PIL import Image
from io import BytesIO

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "indoor_sun"
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Indoor Sun from a config entry."""
    coordinator = IndoorSunCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class IndoorSunCoordinator(DataUpdateCoordinator):
    """Coordinator for Indoor Sun component."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.base_url = entry.data["base_url"]
        self.camera = entry.data["camera"]
        self.scan_interval = entry.data.get("scan_interval", 60)
        
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
            
        # Process image in executor to avoid blocking
        return await self.hass.async_add_executor_job(
            self._process_image, image_data
        )

    def _process_image(self, image_data: bytes) -> Dict[str, Any]:
        """Process the image to calculate brightness and RGB values."""
        with Image.open(BytesIO(image_data)) as img:
            # Convert to RGB if not already
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Get all pixel values
            pixels = list(img.getdata())
            
            # Calculate average RGB
            total_pixels = len(pixels)
            total_r = sum(pixel[0] for pixel in pixels)
            total_g = sum(pixel[1] for pixel in pixels)
            total_b = sum(pixel[2] for pixel in pixels)
            
            avg_r = total_r / total_pixels
            avg_g = total_g / total_pixels
            avg_b = total_b / total_pixels
            
            # Calculate brightness using Y = 0.2126*R + 0.7152*G + 0.0722*B
            brightness_y = 0.2126 * avg_r + 0.7152 * avg_g + 0.0722 * avg_b
            brightness_percent = (brightness_y / 255) * 100
            
            return {
                "brightness": round(brightness_percent, 2),
                "r": round(avg_r),
                "g": round(avg_g),
                "b": round(avg_b),
                "rgb_string": f"{round(avg_r)}, {round(avg_g)}, {round(avg_b)}"
            } 