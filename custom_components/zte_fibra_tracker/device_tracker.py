"""Device tracker platform for ZTE Fibra router."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZteFibraCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZteFibraCoordinator = hass.data[DOMAIN][entry.entry_id]
    tracked: set[str] = set()

    @callback
    def _check_for_new_devices() -> None:
        new_entities = [
            ZteFibraTrackerEntity(coordinator, mac)
            for mac in coordinator.data
            if mac not in tracked
        ]
        if new_entities:
            tracked.update(e.mac_address for e in new_entities)
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_check_for_new_devices))
    _check_for_new_devices()


class ZteFibraTrackerEntity(CoordinatorEntity[ZteFibraCoordinator], ScannerEntity):
    """Represents a single device seen by the ZTE Fibra router."""

    def __init__(self, coordinator: ZteFibraCoordinator, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = mac.replace(":", "_")

    @property
    def source_type(self) -> SourceType:
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        return self._mac in self.coordinator.data

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def ip_address(self) -> str | None:
        return self.coordinator.data.get(self._mac, {}).get("ip") or None

    @property
    def hostname(self) -> str | None:
        return self.coordinator.data.get(self._mac, {}).get("hostname") or None

    @property
    def device_info(self) -> DeviceInfo:
        name = (
            self.coordinator.data.get(self._mac, {}).get("hostname")
            or self._mac
        )
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            name=name,
        )
