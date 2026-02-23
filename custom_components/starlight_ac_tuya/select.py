from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging

_LOGGER = logging.getLogger(__name__)

_SWING_DP = ["gear_vertical", "gear_horizontal"]

_VERTICAL_MAP = {
    "1": "Up-Down Flow",
    "9": "Up Flow",
    "11": "Middle Flow",
    "13": "Down Flow",
}
_VERTICAL_REVERSE = {v: k for k, v in _VERTICAL_MAP.items()}

_HORIZONTAL_MAP = {
    "1": "Left-Right Flow",
    "9": "Left Flow",
    "11": "Middle Flow",
    "13": "Right Flow",
}
_HORIZONTAL_REVERSE = {v: k for k, v in _HORIZONTAL_MAP.items()}


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
        for dp in _SWING_DP:
            if coord.data.get(dp) is None:
                continue
            if dp == "gear_vertical":
                display_name = "Airflow - Vertical"
            elif dp == "gear_horizontal":
                display_name = "Airflow - Horizontal"
            else:
                display_name = dp.replace("_", " ").title()
            entities.append(TuyaACSelect(coord, api, device_id, dp, display_name))

    async_add_entities(entities)


class TuyaACSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, api, device_id, dp_code, name):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self.device_id = device_id
        self.dp_code = dp_code
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_{dp_code}_select"

    @property
    def current_option(self):
        v = self.coordinator.data.get(self.dp_code)
        if v is None:
            return None
        if self.dp_code == "gear_vertical":
            return _VERTICAL_MAP.get(str(v), str(v))
        if self.dp_code == "gear_horizontal":
            return _HORIZONTAL_MAP.get(str(v), str(v))
        return str(v)

    @property
    def options(self):
        v = self.coordinator.data.get(self.dp_code)
        if v is None:
            return []
        if self.dp_code == "gear_vertical":
            return list(_VERTICAL_MAP.values())
        if self.dp_code == "gear_horizontal":
            return list(_HORIZONTAL_MAP.values())
        try:
            iv = int(v)
        except Exception:
            return [str(v)]
        max_opt = max(20, iv + 5)
        return [str(i) for i in range(0, max_opt + 1)]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("starlight_ac_tuya", self.device_id)},
            manufacturer="Star-Light",
        )

    async def async_select_option(self, option: str) -> None:
        try:
            value = option
            if self.dp_code == "gear_vertical":
                value = _VERTICAL_REVERSE.get(option, option)
            elif self.dp_code == "gear_horizontal":
                value = _HORIZONTAL_REVERSE.get(option, option)

            resp = await self.api.async_send_command(
                self.device_id, [{"code": self.dp_code, "value": value}]
            )
            _LOGGER.debug(
                "Select set response for %s %s -> %s",
                self.device_id,
                self.dp_code,
                resp,
            )
            if not (isinstance(resp, dict) and resp.get("success") is False):
                new_data = dict(self.coordinator.data or {})
                new_data[self.dp_code] = value
                await self.coordinator.async_set_updated_data(new_data)
        except Exception as err:
            _LOGGER.error(
                "Failed to set select %s for %s: %s", self.dp_code, self.device_id, err
            )
