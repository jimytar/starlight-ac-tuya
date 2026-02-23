#!/usr/bin/env python3
"""Simple Tuya status / command helper (synchronous, requests).

Usage examples:
  python3 tuya_status.py --client-id ID --client-secret SECRET --status DEVICE_ID
  python3 tuya_status.py --client-id ID --client-secret SECRET --command DEVICE_ID '{"commands":[{"code":"temp_set","value":2400}]}'

Pass --base-url to override region (default https://openapi.tuyaeu.com).
"""

import time
import hmac
import hashlib
import json
import argparse
import requests
from typing import Optional

REGION_URLS = {
    "eu": "https://openapi.tuyaeu.com",
    "us": "https://openapi.tuyaus.com",
    "cn": "https://openapi.tuyacn.com",
    "in": "https://openapi.tuyain.com",
}


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def sign_hmac(msg: str, secret: str) -> str:
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest().upper()


def get_timestamp_ms() -> str:
    return str(int(time.time() * 1000))


class TuyaHelper:
    def __init__(
        self, client_id: str, client_secret: str, base_url: Optional[str] = None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url or REGION_URLS["eu"]
        self.token = None
        self.token_expiry = 0

    def _request(
        self, method: str, path: str, body: str = "", include_token: bool = True
    ):
        t = get_timestamp_ms()
        content_hash = sha256_hex(body)
        string_to_sign = method + "\n" + content_hash + "\n" + "\n" + path
        if include_token and self.token:
            sign_msg = self.client_id + self.token + t + string_to_sign
        else:
            sign_msg = self.client_id + t + string_to_sign
        signature = sign_hmac(sign_msg, self.client_secret)

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

        url = self.base_url + path
        resp = requests.request(method, url, headers=headers, data=body, timeout=10)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def get_token(self) -> str:
        if self.token and time.time() < self.token_expiry - 30:
            return self.token
        path = "/v1.0/token?grant_type=1"
        data = self._request("GET", path, body="", include_token=False)
        result = data.get("result") or {}
        self.token = result.get("access_token")
        expire = result.get("expire_time")
        if self.token is None:
            raise RuntimeError(f"Failed to obtain token: {data}")
        if expire is None:
            self.token_expiry = time.time() + 7000
        else:
            self.token_expiry = time.time() + int(expire)
        return self.token

    def get_status(self, device_id: str):
        self.get_token()
        path = f"/v1.0/iot-03/devices/{device_id}/status"
        data = self._request("GET", path, body="", include_token=True)
        return data.get("result", [])

    def send_command(self, device_id: str, commands: list):
        self.get_token()
        path = f"/v1.0/iot-03/devices/{device_id}/commands"
        body = json.dumps({"commands": commands})
        data = self._request("POST", path, body=body, include_token=True)
        return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret", required=True)
    p.add_argument("--base-url", default=None)
    p.add_argument("--status", help="Device ID to fetch status for")
    p.add_argument(
        "--command", help="Device ID to send command to (use with --command-json)"
    )
    p.add_argument(
        "--command-json",
        help='JSON string for commands, e.g. "{"commands":[{"code":"temp_set","value":2400}]}"',
    )
    args = p.parse_args()

    helper = TuyaHelper(args.client_id, args.client_secret, base_url=args.base_url)

    if args.status:
        status = helper.get_status(args.status)
        print(json.dumps(status, indent=2))
        return

    if args.command and args.command_json:
        try:
            body = json.loads(args.command_json)
        except Exception as e:
            print("Invalid JSON for --command-json:", e)
            return
        commands = body.get("commands")
        if not commands:
            print("No `commands` key found in JSON")
            return
        resp = helper.send_command(args.command, commands)
        print(json.dumps(resp, indent=2))
        return

    p.print_help()


if __name__ == "__main__":
    main()
