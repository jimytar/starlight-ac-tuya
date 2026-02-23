# Starlight AC Tuya

## About This Integration

Specifically designed for **Star-Light AC models** (ACT-09TSWF, ACT-12TSWF, ACT-18TSWF) that use SmartLife with proprietary firmware.

### Why This Integration Exists

Star-Light air conditioners use **custom Tuya data points (DPs)** that are incompatible with the standard Home Assistant Tuya integration. With the default integration, you can **only adjust temperature** - all other features are inaccessible.

This integration provides **full control** by correctly mapping the proprietary DPs:
- All HVAC modes and fan speeds
- Eco mode, health mode
- Display controls and monitoring
 - Horizontal and vertical airflow control (swing) and auto oscillation

Since these models require **cloud-only control**, this integration uses Tuya OpenAPI.

{% if installed %}
## Changes in this version

Full climate control for Star-Light AC units via Tuya OpenAPI.

{% endif %}

## Features

- **Climate Control**: Full climate entity support with temperature control
- **HVAC Modes**: Auto, Cool, Heat, Dry, Fan, Off
- **Temperature Control**: Set target temperature (16-31°C)
- **Fan Modes**: Low, Medium, High, Auto
**Extra Switches**: 
  - Eco mode
  - Turbo (fan boost)
  - Mute (reduced fan noise)
  - Sleep (0/1)
  - Health mode
  - Beep control
  - Fresh air valve
  - Display light
- **Real-time Updates**: Automatic polling for device status
- **Multiple Devices**: Support for multiple AC units

## Setup

You will need:
1. **Tuya IoT Platform credentials**:
   - Access ID / Client ID
   - Access Secret / Client Secret
   - Device ID(s)
2. Tuya project with "Smart Home Devices Management" API access

### Getting Tuya Credentials

1. Go to [Tuya IoT Platform](https://iot.tuya.com/)
2. Create a Cloud Project → Smart Home → select your data center
3. Go to your project → Overview → copy Access ID and Access Secret
4. Go to Devices → Link Tuya App Account → scan QR code in Tuya Smart app
5. Go to API → enable "IoT Core" and "Authorization" API groups
6. Find your device ID in Devices section

Important: ensure all device data points (DP codes) are enabled in your Tuya Cloud project so the integration can access required features. Follow the enable-all-dpcodes guide: https://github.com/azerty9971/xtend_tuya/blob/main/docs/enable_all_dpcodes.md

## Configuration

After installation, add the integration through:
**Settings** → **Devices & Services** → **Add Integration** → **Starlight AC Tuya**

Enter your Tuya credentials when prompted.

## Support

For issues, feature requests, or questions, visit the [GitHub repository](https://github.com/jimytar/starlight-ac-tuya/issues).
