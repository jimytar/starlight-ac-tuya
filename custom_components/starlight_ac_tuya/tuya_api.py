import time
import hmac
import hashlib
import json
import logging
import asyncio
import aiohttp

_LOGGER = logging.getLogger(__name__)


REGION_URLS = {
    "eu": "https://openapi.tuyaeu.com",
    "us": "https://openapi.tuyaus.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # seconds
RETRY_BACKOFF_MULTIPLIER = 2


class TuyaAPI:
    def __init__(
        self,
        client_id,
        client_secret,
        region: str | None = None,
        base_url: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region or "eu"
        self.base_url = base_url or REGION_URLS.get(self.region, REGION_URLS["eu"])
        self._session: aiohttp.ClientSession | None = None
        self.token: str | None = None
        self.token_expiry: float = 0

    def _clear_token(self):
        """Clear cached access token to force refresh on next request."""
        self.token = None
        self.token_expiry = 0
        _LOGGER.debug("Cleared cached access token")

    def _is_token_invalid_error(self, response_data: dict) -> bool:
        """Check if API response indicates token is invalid (error 1010).

        Args:
            response_data: Parsed JSON response from API.

        Returns:
            True if token is invalid, False otherwise.
        """
        if not response_data.get("success"):
            error_code = response_data.get("code")
            error_msg = response_data.get("msg", "").lower()
            # Check for token invalid error (code 1010 or message contains "token")
            return error_code == 1010 or "token" in error_msg
        return False

    async def async_close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _sign(self, string_to_sign: str) -> str:
        return (
            hmac.new(
                self.client_secret.encode(), string_to_sign.encode(), hashlib.sha256
            )
            .hexdigest()
            .upper()
        )

    def _sha256(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def _get_timestamp(self) -> str:
        return str(int(time.time() * 1000))

    async def _ensure_session(self):
        if self._session is None:
            # Increase timeout for slow/unstable connections
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def _async_request(
        self,
        method: str,
        url_path: str,
        body: str = "",
        include_token: bool = True,
        params: dict | None = None,
        retry_count: int = 0,
    ):
        await self._ensure_session()
        t = self._get_timestamp()

        url_path_with_params = url_path
        if params:
            query_parts = []
            for key, value in sorted(params.items()):
                query_parts.append(f"{key}={value}")
            query_string = "&".join(query_parts)
            url_path_with_params = (
                url_path + "?" + query_string if query_string else url_path
            )

        if url_path.startswith("/v2.0/"):
            content_hash = (
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            )
            string_to_sign = (
                method + "\n" + content_hash + "\n\n" + url_path_with_params
            )
        else:
            content_hash = self._sha256(body)
            string_to_sign = method + "\n" + content_hash + "\n\n" + url_path

        if include_token and self.token:
            sign_msg = self.client_id + self.token + t + string_to_sign
        else:
            sign_msg = self.client_id + t + string_to_sign

        signature = self._sign(sign_msg)

        headers = {
            "client_id": self.client_id,
            "sign_method": "HMAC-SHA256",
            "t": t,
            "sign": signature,
        }
        if include_token and self.token:
            headers["access_token"] = self.token
        if body:
            headers["Content-Type"] = "application/json"

        url = self.base_url + url_path_with_params
        session = self._session
        assert session is not None

        try:
            resp = await session.request(method, url, headers=headers, data=body)
            text = await resp.text()
        except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as exc:
            if retry_count < MAX_RETRIES:
                retry_delay = RETRY_DELAY_BASE * (RETRY_BACKOFF_MULTIPLIER**retry_count)
                msg = (
                    "Network error when calling Tuya API %s %s (attempt %d/%d): %s. "
                    "Retrying in %ds..."
                )
                _LOGGER.warning(
                    msg,
                    method,
                    url_path,
                    retry_count + 1,
                    MAX_RETRIES + 1,
                    exc,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                return await self._async_request(
                    method, url_path, body, include_token, params, retry_count + 1
                )
            else:
                _LOGGER.error(
                    "Network error when calling Tuya API %s %s after %d retries: %s",
                    method,
                    url_path,
                    MAX_RETRIES + 1,
                    exc,
                )
                raise

        if resp.status >= 400:
            _LOGGER.debug("Tuya API error %s %s: %s", resp.status, url_path, text)
            resp.raise_for_status()
        try:
            return json.loads(text)
        except Exception:
            return {}

    async def async_get_token(self) -> str:
        if self.token and time.time() < self.token_expiry - 30:
            return self.token

        url_path = "/v1.0/token?grant_type=1"
        data = await self._async_request("GET", url_path, body="", include_token=False)
        result = data.get("result") or {}
        self.token = result.get("access_token")
        expire = result.get("expire_time")
        if expire is None:
            self.token_expiry = time.time() + 7000
        else:
            self.token_expiry = time.time() + int(expire)
        return self.token

    async def async_send_command(self, device_id: str, commands: list):
        """Send command to device with automatic token retry on error 1010."""
        for attempt in range(2):
            await self.async_get_token()
            body_str = json.dumps({"commands": commands})
            url_path = f"/v1.0/iot-03/devices/{device_id}/commands"
            _LOGGER.debug("Sending Tuya command to %s: %s", device_id, commands)
            data = await self._async_request(
                "POST", url_path, body=body_str, include_token=True
            )

            if self._is_token_invalid_error(data):
                if attempt == 0:
                    _LOGGER.warning(
                        "ERROR 1010 (Token Invalid) detected when sending command"
                    )
                    _LOGGER.warning("Device %s token invalid", device_id)
                    _LOGGER.info("Clearing cache for device %s", device_id)
                    self._clear_token()
                    continue
                else:
                    error_msg = data.get("msg", "Unknown error")
                    error_code = data.get("code", "unknown")
                    _LOGGER.error("ERROR 1010 persists after token refresh.")
                    _LOGGER.error("Check your API credentials.")
                    err = "Tuya API error after token refresh: {} (code: {})".format(
                        error_msg, error_code
                    )
                    raise Exception(err)

            _LOGGER.debug("Tuya command response for %s: %s", device_id, data)
            return data

    async def async_get_status(self, device_id: str) -> list:
        """Get device status with automatic token retry on error 1010."""
        for attempt in range(2):
            await self.async_get_token()
            url_path = f"/v1.0/iot-03/devices/{device_id}/status"
            data = await self._async_request(
                "GET", url_path, body="", include_token=True
            )

            if self._is_token_invalid_error(data):
                if attempt == 0:
                    _LOGGER.warning(
                        "ERROR 1010 (Token Invalid) detected when getting status"
                    )
                    _LOGGER.warning("Device %s token invalid", device_id)
                    _LOGGER.info("Clearing cache for device %s", device_id)
                    self._clear_token()
                    continue
                else:
                    error_msg = data.get("msg", "Unknown error")
                    error_code = data.get("code", "unknown")
                    _LOGGER.error("ERROR 1010 persists after token refresh.")
                    _LOGGER.error("Check your API credentials.")
                    err = "Tuya API error after token refresh: {} (code: {})".format(
                        error_msg, error_code
                    )
                    raise Exception(err)

            return data.get("result", [])

    async def async_list_devices(self) -> list:
        """List all devices using v2.0 API with pagination and token retry."""
        all_devices = []
        last_id = None
        page_size = 20
        retry_count = 0
        max_retries = 1

        while True:
            await self.async_get_token()

            params = {"page_size": page_size}
            if last_id:
                params["last_id"] = last_id

            url_path = "/v2.0/cloud/thing/device"
            data = await self._async_request(
                "GET", url_path, body="", include_token=True, params=params
            )

            if self._is_token_invalid_error(data):
                if retry_count < max_retries:
                    _LOGGER.warning(
                        "ERROR 1010 (Token Invalid) detected during device discovery."
                    )
                    _LOGGER.info("Clearing token cache")
                    _LOGGER.info("Retrying device discovery")
                    self._clear_token()
                    retry_count += 1
                    last_id = None
                    continue
                else:
                    error_msg = data.get("msg", "Unknown error")
                    error_code = data.get("code", "unknown")
                    _LOGGER.error("ERROR 1010 persists after token refresh.")
                    _LOGGER.error("Check your API credentials.")
                    err = "Tuya API error after token refresh: {} (code: {})".format(
                        error_msg, error_code
                    )
                    raise Exception(err)

            retry_count = 0

            if not data.get("success"):
                error_msg = data.get("msg", "Unknown error")
                error_code = data.get("code", "unknown")
                _LOGGER.error(
                    "Tuya API error listing devices: %s (code: %s)",
                    error_msg,
                    error_code,
                )
                break

            devices = data.get("result", [])

            if not isinstance(devices, list):
                _LOGGER.error("Expected list of devices, got: %s", type(devices))
                break

            if not devices:
                break

            all_devices.extend(devices)

            if len(devices) < page_size:
                break

            last_id = devices[-1].get("id")
            if not last_id:
                break

            _LOGGER.debug("Fetched %d devices, continuing pagination...", len(devices))

        _LOGGER.info(
            "Successfully fetched %d total devices from Tuya API", len(all_devices)
        )
        return all_devices
