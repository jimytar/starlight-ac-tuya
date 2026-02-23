from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .tuya_api import TuyaAPI
from .coordinator import TuyaACCoordinator

DOMAIN = "starlight_ac_tuya"
PLATFORMS = ["climate", "switch", "number", "fan", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    client_id = entry.data["client_id"]
    client_secret = entry.data["client_secret"]
    region = entry.data.get("region")
    base_url = entry.data.get("base_url")

    api = TuyaAPI(client_id, client_secret, region=region, base_url=base_url)

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "devices": entry.data.get("devices", []),
        "coordinators": {},
    }

    scan_interval = entry.options.get("scan_interval", 120)
    for device in hass.data[DOMAIN][entry.entry_id]["devices"]:
        device_id = device.get("id")
        if not device_id:
            continue
        coordinator = TuyaACCoordinator(
            hass, api, device_id, update_interval_seconds=scan_interval
        )
        hass.data[DOMAIN][entry.entry_id]["coordinators"][device_id] = coordinator
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not data:
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    try:
        await data["api"].async_close()
    except Exception:
        pass

    return unload_ok
