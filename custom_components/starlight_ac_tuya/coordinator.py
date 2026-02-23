from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    # Import for type checking only to satisfy linters without adding runtime dependency
    from .tuya_api import TuyaAPI

_LOGGER = logging.getLogger(__name__)


class TuyaACCoordinator(DataUpdateCoordinator):
    def __init__(
        self, hass, api: "TuyaAPI", device_id: str, update_interval_seconds: int = 120
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Tuya AC {device_id}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self.api = api
        self.device_id = device_id
        self.data = {}

    async def _async_update_data(self):
        try:
            status = await self.api.async_get_status(self.device_id)
            self.data = {dp["code"]: dp["value"] for dp in status}
            _LOGGER.debug("Fetched status for %s: %s", self.device_id, self.data)
            return self.data
        except Exception as e:
            raise UpdateFailed(e)
