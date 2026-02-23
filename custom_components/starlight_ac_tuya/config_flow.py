from __future__ import annotations

import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_validation as cv

from .tuya_api import TuyaAPI

DOMAIN = "starlight_ac_tuya"

AC_CATEGORY = "kt"

_LOGGER = logging.getLogger(__name__)


class StarlightTuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Optional("region", default="eu"): vol.In(
                        ["eu", "us", "cn", "in"]
                    ),
                    vol.Optional("base_url", default=""): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        client_id = user_input[CONF_CLIENT_ID]
        client_secret = user_input[CONF_CLIENT_SECRET]
        region = user_input.get("region")
        base_url = user_input.get("base_url") or None

        devices = []
        api = TuyaAPI(client_id, client_secret, region=region, base_url=base_url)
        try:
            _LOGGER.info("Starting device discovery...")
            devices = await api.async_list_devices()
            _LOGGER.info(
                "Device discovery: fetched %d devices from Tuya API", len(devices)
            )
            if devices:
                for dev in devices:
                    dev_id = dev.get("id")
                    dev_name = dev.get("customName") or dev.get("name")
                    dev_cat = dev.get("category")
                    _LOGGER.info(
                        "  - Device: %s | Name: %s | Category: %s",
                        dev_id,
                        dev_name,
                        dev_cat,
                    )
            else:
                _LOGGER.warning(
                    "Device discovery returned empty list - no devices found"
                )
        except OSError as e:
            _LOGGER.warning(f"Network error during device discovery: {e}")
            _LOGGER.warning("Device discovery failed due to network issues.")
            _LOGGER.warning("You can still use manual device entry.")
            _LOGGER.info(
                "Possible causes: network unreachable, DNS issues, or firewall"
            )
            _LOGGER.info("Also check for intermittent connection issues")
        except Exception as e:
            _LOGGER.warning(f"Device discovery failed (will use manual entry): {e}")
            import traceback

            _LOGGER.debug(f"Discovery error traceback: {traceback.format_exc()}")

        try:
            await api.async_close()
        except Exception:
            pass

        self.context["devices"] = devices
        self.context["client_id"] = client_id
        self.context["client_secret"] = client_secret
        self.context["region"] = region
        if base_url:
            self.context["base_url"] = base_url

        return await self.async_step_devices()

    async def async_step_devices(self, user_input=None):
        all_devices = self.context.get("devices", []) or []

        ac_devices = [d for d in all_devices if d.get("category") == AC_CATEGORY]
        devices_to_show = ac_devices if ac_devices else all_devices

        _LOGGER.info("Device selection - total discovered: %d", len(all_devices))
        _LOGGER.info(
            "AC devices: %d, showing: %d",
            len(ac_devices),
            len(devices_to_show),
        )

        if user_input is None:
            schema_dict = {}

            if devices_to_show:
                device_options = {}
                for device in devices_to_show:
                    did = device.get("id")
                    custom_name = device.get("customName")
                    if custom_name:
                        display = custom_name
                    else:
                        display = device.get("name", "Unknown")
                    device_options[did] = f"{display} ({did})"

                schema_dict[vol.Optional("discovered_device_ids", default=[])] = (
                    cv.multi_select(device_options)
                )
                _LOGGER.info("Showing %d devices in dropdown", len(device_options))

            schema_dict[vol.Optional("manual_device_ids", default="")] = str

            description = (
                "Select discovered devices or enter device IDs manually "
                "(comma-separated)."
            )
            if not devices_to_show:
                description = (
                    "Enter device IDs separated by commas. "
                    "Find device IDs in the Tuya IoT Platform."
                )

            return self.async_show_form(
                step_id="devices",
                data_schema=vol.Schema(schema_dict),
                description_placeholders={
                    "info": description,
                    "discovered_count": len(devices_to_show),
                },
            )

        discovered_ids = user_input.get("discovered_device_ids", []) or []
        manual_ids_raw = user_input.get("manual_device_ids", "")
        manual_ids = [i.strip() for i in manual_ids_raw.split(",") if i.strip()]

        ids = list(set(discovered_ids + manual_ids))

        if not ids:
            schema_dict = {}
            if devices_to_show:
                device_options = {}
                for device in devices_to_show:
                    did = device.get("id")
                    display = device.get("name", "Unknown")
                    device_options[did] = f"{display} ({did})"

                schema_dict[vol.Optional("discovered_device_ids", default=[])] = (
                    cv.multi_select(device_options)
                )
            schema_dict[vol.Optional("manual_device_ids", default="")] = str

            return self.async_show_form(
                step_id="devices",
                data_schema=vol.Schema(schema_dict),
                errors={"base": "no_devices_selected"},
                description_placeholders={"info": "At least one device is required."},
            )

        selected = []
        device_map = {d.get("id"): d for d in all_devices}

        for did in ids:
            if did in device_map:
                device = device_map[did]
                name = device.get("customName", "").strip()
                if not name:
                    name = device.get("name", "").strip()
                if not name:
                    name = device.get("product_name", "").strip()
                if not name:
                    name = did
                selected.append({"id": did, "name": name})
            else:
                selected.append({"id": did, "name": did})

        entry_data = {
            "client_id": self.context.get("client_id"),
            "client_secret": self.context.get("client_secret"),
            "region": self.context.get("region"),
            "base_url": self.context.get("base_url"),
            "devices": selected,
        }

        return self.async_create_entry(title="Starlight Tuya AC", data=entry_data)
