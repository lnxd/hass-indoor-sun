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
    """Set up Indoor Sun from a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Configuration entry containing connection details.

    Returns:
        bool: True if setup was successful.
    """
    _LOGGER.info("Setting up Indoor Sun integration for camera: %s", entry.data.get("camera"))
    
    coordinator = IndoorSunCoordinator(hass, entry)
    
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to initialize Indoor Sun coordinator: %s", err)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    data = {**entry.data, **entry.options}
    platforms = ["sensor"]
    if data.get("enable_image_entity", False):
        platforms.append("image")

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
    _LOGGER.info("Indoor Sun integration setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Configuration entry to unload.

    Returns:
        bool: True if unload was successful.
    """
    _LOGGER.info("Unloading Indoor Sun integration for camera: %s", entry.data.get("camera"))
    
    data = {**entry.data, **entry.options}
    platforms = ["sensor"]
    if data.get("enable_image_entity", False):
        platforms.append("image")
    
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Indoor Sun integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload Indoor Sun integration")

    return unload_ok


class IndoorSunCoordinator(DataUpdateCoordinator[Dict[str, Any]]):  # type: ignore[misc]
    """Data coordinator for Indoor Sun component.
    
    Manages data fetching and processing from Frigate camera API.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            entry: Configuration entry containing connection details.
        """
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
        
        _LOGGER.debug("Initialized coordinator for camera %s with interval %s seconds", 
                     self.camera, self.scan_interval)
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Frigate camera.

        Returns:
            Dict[str, Any]: Processed image data including brightness and RGB values.

        Raises:
            UpdateFailed: If communication with Frigate fails.
        """
        try:
            async with async_timeout.timeout(10):
                return await self._fetch_and_process_frame()
        except Exception as err:
            _LOGGER.error("Error communicating with Frigate camera %s: %s", self.camera, err)
            raise UpdateFailed(f"Error communicating with Frigate: {err}") from err

    async def _fetch_and_process_frame(self) -> Dict[str, Any]:
        """Fetch JPEG frame from Frigate API and process it.

        Returns:
            Dict[str, Any]: Processed image data with brightness and RGB values.

        Raises:
            UpdateFailed: If frame fetch or processing fails.
        """
        session = async_get_clientsession(self.hass)
        url = f"{self.base_url}/api/{self.camera}/latest.jpg"
        
        _LOGGER.debug("Fetching frame from URL: %s", url)
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.warning("Failed to fetch frame from %s: HTTP %s", url, response.status)
                    raise UpdateFailed(f"Failed to fetch frame: HTTP {response.status}")
                
                image_data = await response.read()
                _LOGGER.debug("Successfully fetched frame data: %s bytes", len(image_data))
        except Exception as err:
            _LOGGER.error("Network error fetching frame from %s: %s", url, err)
            raise UpdateFailed(f"Network error: {err}") from err
            
        result: Dict[str, Any] = await self.hass.async_add_executor_job(
            self._process_image, image_data
        )
        return result

    def _process_image(self, image_data: bytes) -> Dict[str, Any]:
        """Process the image to calculate brightness and RGB values.

        Args:
            image_data: Raw JPEG image data.

        Returns:
            Dict[str, Any]: Processed data containing brightness, RGB values, and
                           optionally base64-encoded image data.

        Raises:
            Exception: If image processing fails.
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                original_size = img.size
                
                if self.crop_coordinates:
                    top_left_x, top_left_y, bottom_right_x, bottom_right_y = self.crop_coordinates
                    img = img.crop((top_left_x, top_left_y, bottom_right_x, bottom_right_y))
                    _LOGGER.debug("Cropped image from %s to %s using coordinates %s", 
                                 original_size, img.size, self.crop_coordinates)
                
                pixels = list(img.getdata())
                
                total_pixels = len(pixels)
                total_r = sum(pixel[0] for pixel in pixels)
                total_g = sum(pixel[1] for pixel in pixels)
                total_b = sum(pixel[2] for pixel in pixels)
                
                avg_r = total_r / total_pixels
                avg_g = total_g / total_pixels
                avg_b = total_b / total_pixels
                
                # Calculate brightness using luminance formula
                brightness_y = 0.2126 * avg_r + 0.7152 * avg_g + 0.0722 * avg_b
                brightness_percent = (brightness_y / 255) * 100
                
                result = {
                    "brightness": round(brightness_percent, 2),
                    "r": round(avg_r),
                    "g": round(avg_g),
                    "b": round(avg_b),
                    "rgb_string": f"{round(avg_r)}, {round(avg_g)}, {round(avg_b)}"
                }
                
                _LOGGER.debug("Processed %s pixels: brightness=%.2f%%, RGB=(%d,%d,%d)", 
                             total_pixels, brightness_percent, round(avg_r), round(avg_g), round(avg_b))
                
                if self.enable_image_entity:
                    img_byte_array = BytesIO()
                    img.save(img_byte_array, format='JPEG', quality=85)
                    img_byte_array.seek(0)
                    result["image_data"] = base64.b64encode(img_byte_array.getvalue()).decode('utf-8')
                    _LOGGER.debug("Generated base64 image data for image entity")
                
                return result
                
        except Exception as err:
            _LOGGER.error("Failed to process image data: %s", err)
            raise


async def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
    """Return the options flow.

    Args:
        config_entry: The configuration entry to create options flow for.

    Returns:
        config_entries.OptionsFlow: The options flow instance.
    """
    from .config_flow import IndoorSunOptionsFlow

    return IndoorSunOptionsFlow(config_entry) 