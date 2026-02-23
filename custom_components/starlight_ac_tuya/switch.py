from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data.get("starlight_ac_tuya", {}).get(entry.entry_id)
    if not data:
        return
    api = data["api"]
    coordinators = data["coordinators"]
    devices = data.get("devices", [])

    entities = []
    seen_ids = set()

    for device in devices:
        device_id = device.get("id")
        coord = coordinators.get(device_id)
        if not coord:
            continue

        for dp_code in ["ai_eco_switch", "health", "beep", "light"]:
            unique_id = f"{device_id}_{dp_code}_switch"
            if unique_id not in seen_ids:
                display_name = (
                    "Eco"
                    if dp_code == "ai_eco_switch"
                    else dp_code.replace("_", " ").title()
                )
                entities.append(
                    TuyaACSwitch(coord, api, device_id, dp_code, display_name)
                )
                seen_ids.add(unique_id)

        if coord.data.get("fan_speed_enum") is not None:
            for dp_code, display_name in [("fan_turbo", "Turbo"), ("fan_mute", "Mute")]:
                unique_id = f"{device_id}_{dp_code}_switch"
                if unique_id not in seen_ids:
                    entities.append(
                        TuyaACSwitch(coord, api, device_id, dp_code, display_name)
                    )
                    seen_ids.add(unique_id)

        if coord.data.get("sleep_enum") is not None:
            dp_code = "sleep_enum"
            unique_id = f"{device_id}_{dp_code}_switch"
            if unique_id not in seen_ids:
                entities.append(TuyaACSwitch(coord, api, device_id, dp_code, "Sleep"))
                seen_ids.add(unique_id)

    async_add_entities(entities)


_LOGGER = logging.getLogger(__name__)

ICON_MAP = {
    "ai_eco_switch": "mdi:leaf",
    "fan_turbo": "mdi:fan",
    "fan_mute": "mdi:volume-off",
    "sleep_enum": "mdi:power-sleep",
    "light": "mdi:lightbulb",
    "health": "mdi:pine-tree",
    "beep": "mdi:volume-source",
}


class TuyaACSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, coordinator, api, device_id, dp_code, name):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self.device_id = device_id
        self.dp_code = dp_code
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_{dp_code}_switch"
        self._attr_icon = ICON_MAP.get(dp_code)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        if self.dp_code == "fan_turbo":
            fan_speed = self.coordinator.data.get("fan_speed_enum")
            return fan_speed == "7" or fan_speed == 7
        elif self.dp_code == "fan_mute":
            fan_speed = self.coordinator.data.get("fan_speed_enum")
            return fan_speed == "1" or fan_speed == 1
        elif self.dp_code == "sleep_enum":
            sleep_val = self.coordinator.data.get("sleep_enum")
            return sleep_val == "1" or sleep_val == 1

        return bool(self.coordinator.data.get(self.dp_code, False))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("starlight_ac_tuya", self.device_id)},
            manufacturer="Star-Light",
        )

    async def async_turn_on(self, **kwargs):
        try:
            if self.dp_code == "ai_eco_switch":
                cmds = [{"code": "ai_eco_switch", "value": True}]
            elif self.dp_code == "fan_turbo":
                cmds = [{"code": "fan_speed_enum", "value": "7"}]
            elif self.dp_code == "fan_mute":
                cmds = [{"code": "fan_speed_enum", "value": "1"}]
            elif self.dp_code == "sleep_enum":
                cmds = [{"code": "sleep_enum", "value": "1"}]
            else:
                cmds = [{"code": self.dp_code, "value": True}]

            resp = await self.api.async_send_command(self.device_id, cmds)
            if not (isinstance(resp, dict) and resp.get("success") is False):
                try:
                    new_data = dict(self.coordinator.data or {})
                    new_data[self.dp_code] = True
                    if self.dp_code == "ai_eco_switch":
                        new_data["ai_eco_switch"] = True
                    if self.dp_code == "fan_turbo":
                        new_data["fan_speed_enum"] = "7"
                        new_data["fan_turbo"] = True
                        new_data["fan_mute"] = False
                    if self.dp_code == "fan_mute":
                        new_data["fan_speed_enum"] = "1"
                        new_data["fan_mute"] = True
                        new_data["fan_turbo"] = False
                    if self.dp_code == "sleep_enum":
                        new_data["sleep_enum"] = "1"
                    await self.coordinator.async_set_updated_data(new_data)
                except Exception:
                    _LOGGER.debug(
                        "Could not update coordinator data for %s %s",
                        self.device_id,
                        self.dp_code,
                        exc_info=True,
                    )
        except Exception as err:
            _LOGGER.error(
                "Failed to turn on %s (%s): %s", self.device_id, self.dp_code, err
            )

    async def async_turn_off(self, **kwargs):
        try:
            if self.dp_code == "ai_eco_switch":
                cmds = [{"code": "ai_eco_switch", "value": False}]
            elif self.dp_code == "fan_turbo":
                fan_speed = self.coordinator.data.get("fan_speed_enum")
                sleep_is_on = fan_speed == "1" or fan_speed == 1
                cmds = (
                    [{"code": "fan_speed_enum", "value": "0"}]
                    if not sleep_is_on
                    else []
                )
            elif self.dp_code == "fan_mute":
                fan_speed = self.coordinator.data.get("fan_speed_enum")
                turbo_is_on = fan_speed == "7" or fan_speed == 7
                cmds = (
                    [{"code": "fan_speed_enum", "value": "0"}]
                    if not turbo_is_on
                    else []
                )
            elif self.dp_code == "sleep_enum":
                cmds = [{"code": "sleep_enum", "value": "0"}]
            else:
                cmds = [{"code": self.dp_code, "value": False}]

            resp = await self.api.async_send_command(self.device_id, cmds)
            if not (isinstance(resp, dict) and resp.get("success") is False):
                try:
                    new_data = dict(self.coordinator.data or {})
                    new_data[self.dp_code] = False
                    if self.dp_code == "ai_eco_switch":
                        new_data["ai_eco_switch"] = False
                    if self.dp_code == "fan_turbo":
                        new_data["fan_turbo"] = False
                        fan_speed = new_data.get("fan_speed_enum")
                        if not (fan_speed == "1" or fan_speed == 1):
                            new_data["fan_speed_enum"] = "0"
                    if self.dp_code == "fan_mute":
                        new_data["fan_mute"] = False
                        fan_speed = new_data.get("fan_speed_enum")
                        if not (fan_speed == "7" or fan_speed == 7):
                            new_data["fan_speed_enum"] = "0"
                    if self.dp_code == "sleep_enum":
                        new_data["sleep_enum"] = "0"
                    await self.coordinator.async_set_updated_data(new_data)
                except Exception:
                    _LOGGER.debug(
                        "Could not update coordinator data for %s %s",
                        self.device_id,
                        self.dp_code,
                        exc_info=True,
                    )
        except Exception as err:
            _LOGGER.error(
                "Failed to turn off %s (%s): %s", self.device_id, self.dp_code, err
            )
