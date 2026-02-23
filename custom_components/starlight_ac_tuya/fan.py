from homeassistant.components.fan import FanEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging

_LOGGER = logging.getLogger(__name__)

_FAN_DP_PREFER = ["fan_speed_enum"]

_FAN_ENUM_MAP = {
    "0": "Auto",
    "1": "Silent",
    "3": "Low",
    "5": "Mid",
    "7": "Strong",
}
_FAN_ENUM_REVERSE = {v: k for k, v in _FAN_ENUM_MAP.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    return


class TuyaACFan(CoordinatorEntity, FanEntity):
    def __init__(self, coordinator, api, device_id, name):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self.device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_fan"

    @property
    def is_on(self):
        data = self.coordinator.data
        if data.get("switch") is False:
            return False
        for dp in _FAN_DP_PREFER:
            v = data.get(dp)
            if v is None:
                continue
            try:
                if isinstance(v, bool):
                    return v
                if isinstance(v, str) and v.isdigit():
                    return int(v) > 0
                return int(v) > 0
            except Exception:
                continue
        return False

    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data
        for dp in _FAN_DP_PREFER:
            v = data.get(dp)
            if v is None:
                continue
            try:
                if isinstance(v, str) and v.isdigit():
                    return int(v)
                if isinstance(v, (int, float)):
                    return int(v)
            except Exception:
                continue
        return None

    @property
    def preset_modes(self) -> list[str] | None:
        if self.coordinator.data.get("fan_speed_enum") is None:
            return None
        return list(_FAN_ENUM_MAP.values())

    @property
    def preset_mode(self) -> str | None:
        v = self.coordinator.data.get("fan_speed_enum")
        if v is None:
            return None
        return _FAN_ENUM_MAP.get(str(v), str(v))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("starlight_ac_tuya", self.device_id)},
            manufacturer="Star-Light",
        )

    import logging

    _LOGGER = logging.getLogger(__name__)

    async def async_setup_entry(hass, entry, async_add_entities):
        """No fan entities are created by this integration.

        Fan speed is controlled via Select or helper switches (Turbo/Sleep).
        """
        return
