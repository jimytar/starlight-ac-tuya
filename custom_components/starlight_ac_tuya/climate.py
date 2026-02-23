from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
import logging

try:
    from homeassistant.const import TEMP_CELSIUS
except Exception:
    TEMP_CELSIUS = "°C"
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity


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
        name = device.get("name") or device_id
        coord = coordinators.get(device_id)
        if not coord:
            continue
        entities.append(TuyaACClimate(coord, api, device_id, name))

    async_add_entities(entities)


_LOGGER = logging.getLogger(__name__)


class _FeatureMask(int):
    """Integer mask that also supports `in` checks for ClimateEntityFeature.

    This lets the integration be compatible with HA versions that expect
    an iterable (supporting `in`) as well as versions that use bitwise
    operations on an integer mask.
    """

    def __contains__(self, item):
        try:
            return (self & int(item)) == int(item)
        except Exception:
            return False


class TuyaACClimate(CoordinatorEntity, ClimateEntity):
    def __init__(self, coordinator, api, device_id, name):
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.api = api
        self.device_id = device_id
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_climate"

    @property
    def hvac_modes(self):
        return [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]

    @property
    def hvac_mode(self):
        data = self.coordinator.data
        if not data.get("switch", True):
            return HVACMode.OFF
        mode_val = data.get("mode")
        if mode_val is not None:
            try:
                m = str(mode_val)
                mode_map = {
                    "0": HVACMode.AUTO,
                    "1": HVACMode.COOL,
                    "2": HVACMode.DRY,
                    "3": HVACMode.FAN_ONLY,
                    "4": HVACMode.HEAT,
                }
                return mode_map.get(m, HVACMode.AUTO)
            except Exception:
                return HVACMode.AUTO

        return HVACMode.COOL

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self.coordinator.data.get("temp_current", 0) / 100

    @property
    def target_temperature(self):
        return self.coordinator.data.get("temp_set", 0) / 100

    @property
    def target_temperature_step(self):
        """Return the temperature step for the HVAC controls (1°C)."""
        return 1.0

    @property
    def supported_features(self):
        return _FeatureMask(int(ClimateEntityFeature.TARGET_TEMPERATURE))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={("starlight_ac_tuya", self.device_id)},
            name=self._attr_name,
            manufacturer="Star-Light",
        )

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is None:
            return
        try:
            resp = await self.api.async_send_command(
                self.device_id, [{"code": "temp_set", "value": int(temp * 100)}]
            )
            if not (isinstance(resp, dict) and resp.get("success") is False):
                try:
                    new_data = dict(self.coordinator.data or {})
                    new_data["temp_set"] = int(temp * 100)
                    await self.coordinator.async_set_updated_data(new_data)
                except Exception:
                    _LOGGER.debug(
                        "Could not update coordinator data for temperature for %s",
                        self.device_id,
                        exc_info=True,
                    )
        except Exception as err:
            _LOGGER.error("Error setting temperature for %s: %s", self.device_id, err)

    async def async_set_hvac_mode(self, hvac_mode):
        hvac_to_mode = {
            HVACMode.AUTO: "0",
            HVACMode.COOL: "1",
            HVACMode.DRY: "2",
            HVACMode.FAN_ONLY: "3",
            HVACMode.HEAT: "4",
        }
        mode_value = hvac_to_mode.get(hvac_mode, "0")
        commands = [
            {"code": "switch", "value": hvac_mode != HVACMode.OFF},
            {"code": "mode", "value": mode_value},
        ]
        try:
            resp = await self.api.async_send_command(self.device_id, commands)
            if not (isinstance(resp, dict) and resp.get("success") is False):
                try:
                    new_data = dict(self.coordinator.data or {})
                    new_data["switch"] = hvac_mode != HVACMode.OFF
                    new_data["mode"] = mode_value
                    await self.coordinator.async_set_updated_data(new_data)
                except Exception:
                    _LOGGER.debug(
                        "Could not update coordinator data for HVAC mode for %s",
                        self.device_id,
                        exc_info=True,
                    )
        except Exception as err:
            _LOGGER.error("Error setting HVAC mode for %s: %s", self.device_id, err)
