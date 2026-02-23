from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging

_LOGGER = logging.getLogger(__name__)

_NUMERIC_DP_CANDIDATES = []


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data.get("starlight_ac_tuya", {}).get(entry.entry_id)
    if not data:
        return
    api = data["api"]
    coordinators = data["coordinators"]
    devices = data.get("devices", [])

    entities = []
    for device in devices:
        device_id = device.get("id")
        coord = coordinators.get(device_id)
        if not coord:
            continue
        for dp in _NUMERIC_DP_CANDIDATES:
            display_name = dp.replace("_", " ").title()
            entities.append(TuyaACNumber(coord, api, device_id, dp, display_name))

    async_add_entities(entities)


class TuyaACNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, api, device_id, dp_code, name):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self.device_id = device_id
        self.dp_code = dp_code
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_{dp_code}_number"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1

    @property
    def native_value(self):
        val = self.coordinator.data.get(self.dp_code)
        if val is None:
            return None
        try:
            return float(val)
        except Exception:
            return None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("starlight_ac_tuya", self.device_id)},
            manufacturer="Star-Light",
        )

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.api.async_send_command(
                self.device_id, [{"code": self.dp_code, "value": value}]
            )
            try:
                new_data = dict(self.coordinator.data or {})
                new_data[self.dp_code] = value
                await self.coordinator.async_set_updated_data(new_data)
            except Exception:
                _LOGGER.debug(
                    "Could not optimistically update %s %s",
                    self.device_id,
                    self.dp_code,
                    exc_info=True,
                )
        except Exception as err:
            _LOGGER.error(
                "Failed to set numeric DP %s for %s: %s",
                self.dp_code,
                self.device_id,
                err,
            )
