"""DataUpdateCoordinator for ZTE Fibra router."""
from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

# mac -> {"hostname": str, "ip": str}
DeviceData = dict[str, dict[str, str]]


class ZteFibraCoordinator(DataUpdateCoordinator[DeviceData]):
    """Polls the ZTE Fibra router for connected devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(hass, _LOGGER, name="ZTE Fibra", update_interval=update_interval)
        self.host = host
        self.username = username
        self.password = password
        self._base_url = f"https://{host}"

    async def _async_update_data(self) -> DeviceData:
        try:
            return await self._fetch_devices()
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unexpected error communicating with router: {err}") from err

    async def _fetch_devices(self) -> DeviceData:
        # CookieJar(unsafe=True) allows cookies on IP addresses (router is at 192.168.1.1)
        jar = aiohttp.CookieJar(unsafe=True)
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            cookie_jar=jar,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self._base_url}/",
            },
        ) as session:
            # Step 1: GET login_entry to obtain pre-login token (CSRF protection)
            async with session.get(
                f"{self._base_url}/?_type=loginData&_tag=login_entry",
                ssl=False,
                timeout=timeout,
            ) as resp:
                try:
                    pre_data = await resp.json(content_type=None)
                except Exception as err:
                    raise UpdateFailed(f"Unexpected login response: {err}") from err
                pre_token = pre_data.get("sess_token", "")
                if not pre_token:
                    raise UpdateFailed("Router did not return a pre-login token")

            # Step 2: GET login_token to obtain challenge
            async with session.get(
                f"{self._base_url}/?_type=loginData&_tag=login_token",
                ssl=False,
                timeout=timeout,
            ) as resp:
                xml_text = await resp.text()
            try:
                challenge = ET.fromstring(xml_text).text or ""
            except ET.ParseError as err:
                raise UpdateFailed(f"Failed to parse challenge: {err}") from err

            # Step 3: POST login with hashed password + CSRF token
            pwd_hash = hashlib.sha256(f"{self.password}{challenge}".encode()).hexdigest()
            async with session.post(
                f"{self._base_url}/?_type=loginData&_tag=login_entry",
                data={
                    "action": "login",
                    "Username": self.username,
                    "Password": pwd_hash,
                    "_sessionTOKEN": pre_token,
                },
                ssl=False,
                timeout=timeout,
            ) as resp:
                try:
                    login = await resp.json(content_type=None)
                except Exception as err:
                    raise UpdateFailed(f"Unexpected login response: {err}") from err

            locking = login.get("lockingTime", 0)
            if isinstance(locking, (int, float)) and locking > 0:
                raise UpdateFailed(f"Router login locked for {locking}s (too many failed attempts)")
            sess = login.get("sess_token")
            if not sess:
                raise UpdateFailed(
                    f"Login failed: {login.get('loginErrMsg') or 'unknown error'}"
                )

            # Manually set the session cookie (router returns it in body, not Set-Cookie)
            jar.update_cookies({"sess_token": sess})

            # Prime the session — router sets SID cookie and activates the session
            async with session.get(
                f"{self._base_url}/",
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                await resp.read()

            # Fetch all connected devices
            async with session.get(
                f"{self._base_url}/?_type=hiddenData&_tag=accessdev_data&DeveiceType=ALL",
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                devices_xml = await resp.text()

            # Logout (best-effort — don't fail the update if this errors)
            try:
                async with session.post(
                    f"{self._base_url}/?_type=loginData&_tag=logout_entry",
                    data={"IF_LogOff": "1"},
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    await resp.read()
            except Exception:
                pass

        result = self._parse_devices(devices_xml)
        _LOGGER.debug("Found %d device(s) connected to router", len(result))
        return result

    @staticmethod
    def _parse_devices(xml_text: str) -> DeviceData:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as err:
            raise UpdateFailed(f"Failed to parse router response: {err}") from err

        error = root.findtext("IF_ERRORSTR", "")
        if error and error != "SUCC":
            raise UpdateFailed(f"Router API error: {error}")

        devices: DeviceData = {}
        for instance in root.findall(".//OBJ_ACCESSDEV_ID/Instance"):
            # Children alternate: <ParaName>key</ParaName><ParaValue>val</ParaValue>
            children = list(instance)
            params: dict[str, str] = {}
            for i in range(0, len(children) - 1, 2):
                if children[i].tag == "ParaName" and children[i + 1].tag == "ParaValue":
                    params[children[i].text or ""] = children[i + 1].text or ""

            mac = params.get("_LuQUID_MACAddress", "").lower()
            if mac:
                devices[mac] = {
                    "hostname": params.get("_LuQUID_HostName", ""),
                    "ip": params.get("_LuQUID_IPAddress", ""),
                }

        return devices
