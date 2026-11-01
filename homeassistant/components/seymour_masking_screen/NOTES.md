# Seymour Masking Screen Integration Notes

_Last updated: 2026-02-22_

## Overview

Home Assistant integration for **Seymour Screen Excellence** motorized masking
screens.  The screen masks (top, bottom, left, right, horizontal, vertical) are
controlled by a Seymour controller connected either via direct RS232 serial or
through a **Global Caché iTach IP2SL** TCP-to-serial bridge.

---

## seymourlib — upstream library

| Key | Value |
|---|---|
| GitHub | <https://github.com/richard-berg/seymourlib\> |
| PyPI | <https://pypi.org/project/seymourlib/\> |
| Pinned version | **0.1.4** (bump from 0.1.3; adds async serial discovery) |
| Maturity | Alpha (`Development Status :: 3 - Alpha`) — single author, MIT, `py.typed` |
| Dependencies | `anyio>=3.4`, `attrs>=25.4.0`, `tenacity>=8.0`, `async-typer`; optional `[serial]` adds `pyserial-asyncio` |
| CI/CD | GitHub Actions, Codecov badge present |

### Client API (`seymourlib.client.SeymourClient`)

Async context manager.  All public methods are `async`.

| Category | Methods |
|---|---|
| **Queries** | `get_status()`, `get_positions()`, `get_system_info()`, `get_ratio_settings()`, `get_diagnostics(option)` |
| **Movement** | `move_out(motor, movement)`, `move_in(motor, movement)`, `move_to_ratio(ratio)` |
| **Control** | `home(motor)`, `halt(motor)`, `calibrate(motor)` |
| **Config** | `update_ratio(ratio)`, `reset_factory_default(ratio?)` |
| **Lifecycle** | `connect()`, `close()`, `start_health_monitoring()`, `is_connected`, `connection_stats` |

- Motion commands block until controller reports `HALTED`/`STOPPED_AT_RATIO`.
- Internal `asyncio.Lock` serializes all operations (single-writer design).
- Built-in retry via `tenacity`, health-check background loop, auto-reconnect.

### Transport layer

- `TCPTransport(host, port=4999)` — for Global Caché IP2SL bridge.
- `SerialTransport(port, baudrate=115200)` — direct USB/RS232.
- Both use `asyncio.StreamReader`/`StreamWriter`.
- Constant: `ITACH_SERIAL_PORT = 4999`.

### Protocol types (`seymourlib.protocol`)

| Type | Fields |
|---|---|
| `MaskStatus` | `.code` (StatusCode enum), `.ratio` (Ratio or None) |
| `MaskPosition` | `.motor_id` (MotorID enum), `.position_pct` (float 0–100) |
| `SystemInfo` | `.screen_model`, `.serial_number` (Serial obj — use `.to_serial_number()` for str), `.mask_ids`, `.width_inches`, `.height_inches` |
| `RatioSetting` | `.ratio` (.id str), `.label` (str or None), geometry fields |
| `StatusCode` | `STOPPED_AT_RATIO`, `MOVING_TO_RATIO`, `HALTED`, `HOMING`, `CALIBRATING`, `MOVING_OUTWARD`, `MOVING_INWARD`, `ERROR` |
| `MotorID` | `TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `VERTICAL`, `HORIZONTAL`, `ALL` |
| `MovementCode` | `UNTIL_LIMIT`, `JOG`, `MOVE` |
| `DiagnosticOption` | `LIST_FS`, `LIST_SETTINGS_JSON`, `LIST_SYSTEM_JSON` |
| `Ratio` | Wrapper with `.id` (str) |

### Discovery (`seymourlib.discovery`)

- `enumerate_tcp_transports(interval?, interface_ip?)` — multicast listener for Global Caché AMX beacons; returns `TCPTransportCandidate` with `.host`, `.port`, `.metadata`, `.raw_beacon`.
- `enumerate_serial_transports(baudrate?)` — lists serial adapters; returns `SerialTransportCandidate` with `.device`, `.description`, `.hardware_id`, `.baudrate`.
- `DiscoveryError` exception.

### Exceptions

- `SeymourError` — base.
- `SeymourConnectionError(SeymourError)` — transport-level failures.
- `SeymourProtocolError(SeymourError)` — unexpected response parsing.
- `SeymourTransportError(SeymourError)` — low-level transport I/O errors.

### Known limitations

- **No push/websocket** — all data must be polled.
- Single-writer lock means concurrent callers queue up.
- Alpha maturity: API surface may change.

### Buffer desynchronisation fix (seymourlib ≥ 0.1.5)

The IP2SL bridge and RS-232 transport are strictly half-duplex.  When the
status coordinator made two independent calls (`get_status()` then
`get_positions()`), each acquired and released the client lock
independently.  Between these calls, a stale or delayed frame could
appear in the TCP read buffer, causing `get_positions()` to consume
the wrong response.  This created a self-sustaining off-by-one cascade
(alternating success/failure every poll cycle).

Fixes applied in seymourlib:

1. **Buffer drain before send** — `drain_read_buffer()` discards any
   stale bytes before each send operation.  This is the primary fix:
   every `_execute_operation` call drains the buffer before sending,
   so a stale frame left by a previous timed-out or mismatched
   request is discarded rather than consumed by the next `receive()`.
2. **`TCPTransport.connect()` closes existing socket** before opening a
   new one, preventing TCP socket leaks on the single-connection IP2SL.
3. **`_send_and_maybe_receive` no longer marks `_connected = False`
   for non-transport errors** — protocol errors (malformed but received
   frame) don't trigger unnecessary reconnection attempts.

Integration-side workaround:

- After `_RECONNECT_AFTER_FAILURES` (5) consecutive connection errors,
  the coordinator forces a full `close()` + `connect()` cycle to reset
  the IP2SL bridge state.

### IP2SL single-connection constraint

The Global Caché IP2SL **accepts only one TCP connection per serial port** at a
time.  A second `connect()` to the same `host:port` will either hang until the
first connection is dropped or be refused outright.  This has several
implications for integration code:

1. **Exactly one `SeymourClient` instance per config entry at any time.**
   Creating a second client (e.g., for validation) while a previous one is
   still connected will deadlock or fail.

2. **Every code path that calls `client.connect()` must guarantee a matching
   `client.close()` on all exit paths** — including exceptions, coordinator
   first-refresh failures, and `ConfigEntryNotReady` retries.  If `close()`
   is missed the orphaned socket holds the IP2SL slot and all subsequent
   connection attempts fail.

3. **Config flow validation must fully close its client** before
   `async_setup_entry` creates and connects its own.  The `finally` block
   in `_async_validate_connection` handles this.

4. **`async_setup_entry` must close the client** if any step after
   `connect()` fails (e.g., coordinator first-refresh raising
   `ConfigEntryNotReady`).  HA does **not** call `async_unload_entry` when
   setup raises `ConfigEntryNotReady`, so cleanup must happen in-line.

5. **Health monitoring** (`client.start_health_monitoring()`) should be
   started only after coordinator first-refresh succeeds, since it spawns a
   background task that would leak alongside the client on setup failure.

---

## Architecture of this integration

### File layout

```
homeassistant/components/seymour_masking_screen/
├── __init__.py          # async_setup_entry / async_unload_entry
├── manifest.json        # domain, requirements, quality_scale
├── const.py             # DOMAIN, ConnectionType, polling intervals
├── models.py            # SeymourRuntimeData dataclass
├── config_flow.py       # user/manual_serial/manual_ip/reauth/reconfigure steps
├── coordinator.py       # SeymourStatusCoordinator, SeymourMetadataCoordinator, SeymourDiagnosticsStore
├── discovery.py         # Wraps seymourlib discovery for config flow
├── entity.py            # SeymourEntity, SeymourMetadataEntity base classes
├── cover.py             # [TO ADD] CoverEntity — primary control surface
├── button.py            # Motor home/halt/calibrate + diagnostics buttons
├── select.py            # Ratio move/update/reset, directional move selects
├── sensor.py            # Status enum, ratio, connection age, positions, dimensions, diagnostics text
├── diagnostics.py       # Config entry diagnostics with redacted data
├── strings.json         # All user-facing text
├── quality_scale.yaml   # Rule status tracking
├── NOTES.md             # This file — background research & decisions
└── TODO.md              # Actionable task list
tests/components/seymour_masking_screen/
├── __init__.py
├── conftest.py          # [TO ADD] Shared fixtures & mock client factory
├── test_config_flow.py  # 6 tests (needs expansion)
├── test_init.py         # [TO ADD]
├── test_cover.py        # [TO ADD]
├── test_button.py       # [TO ADD]
├── test_select.py       # [TO ADD]
├── test_sensor.py       # [TO ADD]
├── test_coordinator.py  # [TO ADD]
├── test_diagnostics.py  # [TO ADD]
└── snapshots/           # [TO ADD] syrupy snapshot files
```

### Config entry data model

Stored in `ConfigEntry.data`:

```python
{
    "connection_type": "serial" | "ip2sl",
    "serial_port": "/dev/ttyUSB0",     # when serial
    "host": "192.168.1.70",            # when ip2sl
    "port": 4999,                      # when ip2sl (optional, defaults to 4999)
}
```

Unique ID = `SystemInfo.serial_number.to_serial_number()` (string from controller EEPROM).

### Runtime data (`SeymourRuntimeData`)

```python
@dataclass
class SeymourRuntimeData:
    client: SeymourClient
    status_coordinator: SeymourStatusCoordinator      # fast: 1–5s adaptive
    metadata_coordinator: SeymourMetadataCoordinator   # slow: 5min
    diagnostics: SeymourDiagnosticsStore               # dispatcher-based
    device_info: DeviceInfo
```

### Coordinators

| Coordinator | Polls | Interval | Adaptation |
|---|---|---|---|
| `SeymourStatusCoordinator` | `get_status()` + `get_positions()` | 2s default | 1s while moving, 5s when idle |
| `SeymourMetadataCoordinator` | `get_system_info()` + `get_ratio_settings()` | 5 min | Refresh on demand after ratio changes |

Status coordinator tracks consecutive failures and raises a **repair issue** (`transport_unreachable`) after 3.

### Entity architecture

Both base entity classes set `_attr_has_entity_name = True` and carry `device_info`.

- `SeymourEntity(CoordinatorEntity[SeymourStatusCoordinator])` — fast-updating entities; also subscribes to metadata coordinator listener for ratio label updates.
- `SeymourMetadataEntity(CoordinatorEntity[SeymourMetadataCoordinator])` — slow-updating entities only.

**Critical gap (pre-existing code):** No entity sets `_attr_unique_id`.
Pattern to follow: `self._attr_unique_id = f"{serial_number}_{entity_key}"`.

### Platforms

| Platform | Entities | Primary/Secondary |
|---|---|---|
| **cover** (TO ADD) | Per-motor CoverEntity; `device_class=SHADE`; features: OPEN/CLOSE/STOP + SET_POSITION via ratio | **Primary** |
| sensor | Status enum, ratio, connection age, per-motor position, dimensions, diagnostics text | Secondary |
| button | Home/halt/calibrate per motor+ALL, diagnostics triggers | Secondary (config/diagnostic) |
| select | Ratio move/update/reset, directional move in/out | Secondary (config) |

---

## Decisions made

1. **CoverEntity is the primary control surface.** Maps: `open_cover` → `move_out(ALL, UNTIL_LIMIT)`, `close_cover` → `move_in(ALL, UNTIL_LIMIT)`, `stop_cover` → `halt(ALL)`, `set_cover_position` → `move_to_ratio`. Device class = `CoverDeviceClass.SHADE`.
2. **Target Gold quality scale** from the initial PR.  Most Gold rules are already partially implemented (diagnostics, repair issues, entity translations, discovery, reconfig flow, etc.).
3. **Bump seymourlib to 0.1.4** — includes async serial discovery fixes.
4. **Devcontainer changes** (`--network=host`, `--device=/dev/ttyUSB0`) kept in a separate commit; will be dropped via interactive rebase before upstream PR.
5. **Two coordinators remain** — the fast/slow split matches the device well (status changes sub-second during movement; metadata is near-static).

---

## Development environment

Runs in a VSCode DevContainer on an Ubuntu/Proxmox host.  Container uses
`--network=host` to receive Global Caché AMX multicast beacons and
`--device=/dev/ttyUSB0` for optional direct serial.  Confirmed that
`seymourctl discover tcp` finds the IP2SL on the local network.

---

## Reference integrations studied

- `hunterdouglas_powerview` — cover entity pattern, `CoverDeviceClass.SHADE`, `PARALLEL_UPDATES = 1`.
- `motion_blinds` — DHCP discovery, cover device class.
- `brunt` — simple cloud-polling cover.
- All use `_attr_unique_id = f"{serial}_{key}"` pattern in entity `__init__`.

---

## Snapshot testing

Entity snapshots live in
`tests/components/seymour_masking_screen/snapshots/test_snapshots.ambr`.
They capture every entity's registry entry and state for each platform
(button, cover, select, sensor) and act as a regression guard.

### Running snapshot tests

```bash
# Verify current snapshots still match:
pytest tests/components/seymour_masking_screen/test_snapshots.py -v

# After intentional changes to entities (new entity, renamed attribute,
# changed device class, etc.), regenerate the snapshots:
pytest tests/components/seymour_masking_screen/test_snapshots.py --snapshot-update

# Then always re-run WITHOUT --snapshot-update to confirm they pass:
pytest tests/components/seymour_masking_screen/test_snapshots.py -v
```

### When to regenerate

Regenerate snapshots whenever you intentionally change something that
affects entity registration or state output:

- Adding, removing, or renaming entities
- Changing `device_class`, `entity_category`, `translation_key`, or `unique_id`
- Changing default state values or attributes in the mock fixtures
- Modifying `DeviceInfo` fields (manufacturer, model, etc.)

**Always review the diff** in the `.ambr` file before committing to make
sure only expected changes appear.
