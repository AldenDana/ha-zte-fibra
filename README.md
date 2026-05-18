# ZTE Fibra Router Tracker for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/AldenDana/ha-zte-fibra.svg)](https://github.com/AldenDana/ha-zte-fibra/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration that tracks devices connected to **ZTE FIBRA** routers — the router deployed by **Orange Spain** as the "Livebox 6s" since 2025.

> **Why this exists:** The standard `sagemcom_fast` integration stopped working when Orange Spain silently replaced Sagemcom hardware with ZTE FIBRA6S units. No existing HACS integration supports the ZTE `hiddenData` API used by this router.

---

## Supported Devices

| Router | ISP | Status |
|---|---|---|
| ZTE FIBRA6S (`ZTEGFIBRA6S`) | Orange Spain | ✅ Confirmed working |

Other ZTE FIBRA models using the same `hiddenData` API are likely compatible. Open an issue if you confirm one.

---

## Features

- Discovers all devices currently connected to the router (Wi-Fi + wired)
- Creates a `device_tracker` entity for each connected MAC address
- Exposes **hostname**, **IP address**, and **MAC address** per device
- Links tracker entities to HA's device registry via MAC — merges with existing devices from other integrations (cameras, phones, etc.)
- Configurable scan interval (10–300 seconds)
- UI-only setup via Config Flow — no YAML required
- Proper session management: logs in and out on every poll, no persistent session

---

## Installation

### Via HACS (recommended)

1. Open HACS → Integrations → three-dot menu → **Custom repositories**
2. Add `https://github.com/AldenDana/ha-zte-fibra` as category **Integration**
3. Search for **ZTE Fibra Router Tracker** and install
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/zte_fibra_tracker/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ZTE Fibra Router Tracker**
3. Enter:
   - **Host**: Router IP address (default `192.168.1.1`)
   - **Username**: Router admin username (default `admin`)
   - **Password**: Router admin password
4. The integration will test the connection and create tracker entities for all currently connected devices

### Options

After setup, click **Configure** on the integration card to adjust:
- **Scan interval**: How often to poll the router (10–300 seconds, default 30s)

---

## How It Works

The ZTE FIBRA6S exposes a `hiddenData` HTTP API that requires a 3-step authentication:

1. `GET /?_type=loginData&_tag=login_entry` → retrieves a CSRF token
2. `GET /?_type=loginData&_tag=login_token` → retrieves a challenge string
3. `POST /?_type=loginData&_tag=login_entry` with `Password=SHA256(password + challenge)` and the CSRF token

Connected devices are fetched from `/?_type=hiddenData&_tag=accessdev_data&DeveiceType=ALL` (note: firmware typo in `DeveiceType` is intentional) which returns an XML list of MAC addresses, hostnames, and IPs.

The integration uses `aiohttp` with `CookieJar(unsafe=True)` to handle cookies on IP-address hosts, and disables SSL verification for the router's self-signed certificate.

---

## Usage with Presence Detection

Each discovered device gets a `device_tracker.zte_fibra_tracker_<mac>` entity. You can use these directly in automations or link them to [Persons](https://www.home-assistant.io/integrations/person/) for presence detection:

```yaml
- condition: state
  entity_id: device_tracker.zte_fibra_tracker_ca_a6_33_92_f7_e8
  state: home
```

> **Note on MAC randomization:** Modern Android and iOS devices use per-network randomized MACs. The MAC assigned to your network is stable as long as the Wi-Fi SSID doesn't change, but will change if you reset the network settings or change the SSID.

---

## Troubleshooting

**Cannot connect during setup**
- Verify the router is reachable at the configured IP
- Confirm your admin credentials work at `https://192.168.1.1`
- Check that no other session is open in a browser (the router has a single-session limit)

**Devices not appearing**
- Only currently connected devices are returned by the router API
- Devices that were seen previously will show as `not_home` but remain as entities

**Enable debug logging**
```yaml
logger:
  logs:
    custom_components.zte_fibra_tracker: debug
```

---

## Contributing

Pull requests welcome. If you have a different ZTE FIBRA model and can capture the API responses, open an issue with the output and we can add support.

---

## Acknowledgements

- [juacas/zte_tracker](https://github.com/juacas/zte_tracker) — prior work on ZTE router integrations for Home Assistant; the 3-step authentication flow was first documented there and served as a reference for understanding the ZTE login API.

---

## License

MIT — see [LICENSE](LICENSE)
