# Seymour Masking Screen — Implementation TODO

_Last updated: 2026-11-01_

## Status (Nov 2026)

This branch (`rberg-wip`, based on 2026.2.3) is now a historical snapshot.
Active work lives on branch `seymour-masking-screen` (worktree
`/workspaces/ha-dev`, based on upstream `dev`, Python 3.14 venv in `.venv`).
It holds a minimal bronze-scope first PR: config flow + cover only.
The remaining platforms below come back as follow-up PRs.

seymourlib `serialx-migration` branch (unreleased 0.2.0) replaces
pyserial-asyncio (forbidden by hassfest, blocked in HA since 2026.7) with
serialx, adds `URLTransport`, strips serial-number padding, and fixes
`SeymourClient.close()` leaking the IP2SL socket after a failed request.

Next steps:

- [ ] Merge + tag `v0.2.0` in seymourlib (tag triggers PyPI publish)
- [ ] Write the home-assistant.io docs PR (unblocks bronze `docs-*` rules)
- [ ] Re-submit brands PR as `core_integrations/seymour_masking_screen`,
  linking the core PR (see home-assistant/brands#9134 review)
- [ ] Flip `brands` + bronze `docs-*` to `done`, run hassfest, open core PR
- [ ] Phase 8 hardware checks for movement (open/close/stop) on the new code
- [ ] Follow-up PRs: sensors, ratio select, buttons, diagnostics, repairs,
  reconfigure flow

_Original target (superseded by the minimal first PR above): Gold quality
scale from the initial upstream PR._

See [NOTES.md](NOTES.md) for background research, library API reference, and
architecture decisions.

---

## Phase 8: Real-device validation

Must be done against the actual Seymour controller + IP2SL.

### 8.1 End-to-end smoke test

- [ ] Install integration from dev container HA instance
- [ ] Run config flow -> verify IP2SL discovery shows the device
- [ ] Verify all entities appear with correct initial state
- [ ] Open/close cover -> verify position updates in near-real-time
- [ ] Move to ratio -> verify position tracks correctly
- [ ] Halt mid-movement -> verify stop works
- [ ] Home all masks -> verify

### 8.2 Connection resilience

- [ ] Power-cycle IP2SL -> verify integration recovers
- [ ] Unplug RS232 cable -> verify repair issue appears after 3 failures
- [ ] Replug -> verify repair issue clears and entities recover
- [ ] Leave running 24h+ -> verify no memory leaks or socket exhaustion

### 8.3 Adaptive polling validation

- [ ] While idle: verify 5s intervals (debug log timestamps)
- [ ] Trigger movement: verify interval drops to 1s
- [ ] After movement stops: verify interval returns to 5s
- [ ] Check CPU usage during extended movement -- should be negligible

### 8.4 Edge cases

- [ ] Send command while another is in progress -> verify lock serialization
- [ ] Rapidly toggle cover open/close -> verify no protocol errors
- [ ] Diagnostics buttons -> verify text sensor updates with payload
- [ ] Reconfigure flow -> change IP -> verify reconnection

### 8.5 UX Feedback
- Config flow: choices should be clearer, reordered, and trimmed.  Don't think manual-serial is necessary, unless you
  see gaps in the detection logic that would miss an available serial device?
    - Detected: IP2SL...
    - Detected: Serial...
    - Manual: Enter IP & Port of Global Caché IP2SL
- Config flow: eliminate label "Device or setup option"
- Config flow: for manual IP entry, clarify that the port should be one that carries raw serial data (typically 4999 & above), not the device's control plane (typically 4998).
- Choosing a serial port that doesn't speak Seymour protocol takes too long to timeout, and gives "Unknown error occurred" - make friendlier message along the lines of "are you sure this is the port where your Seymour screen controller is plugged in?"
- Config flow: add "back" button to cancel out of entering custom IP / custom port and return to main picker.  If you exit the flow completely, you have to wait for the integration to rerun the discovery (long).

- Choosing correct IP, it detects screen name, but says "Failed setup, will retry: Unexpected Seymour protocol error"
    - reload: hangs forever on Initializing
    - reconfigure: seems to succeed, then same issue
    - delete: still hung on Initializing
- Restart: no device or integration in UI, but trying to add again says "This Seymour masking screen is already configured."

---

## Phase 9: Pre-PR cleanup

- [ ] Revert `.devcontainer/devcontainer.json` changes (interactive rebase or drop commit)
- [ ] Run `python -m script.hassfest` -- verify all generated files are correct
- [ ] Run `python -m script.translations develop --all` -- verify translations compile
- [ ] Run `prek run --all-files` -- fix any linting issues
- [ ] Run `mypy homeassistant/components/seymour_masking_screen` -- fix type errors
- [ ] Run full test suite with coverage report
- [ ] Verify coverage > 95%
- [ ] Review all snapshot files for correctness
- [ ] Final read-through of all code for HA conventions compliance

---

## Phase 10: Platinum quality scale (remaining)

_Code tasks (10.1–10.5) are done. Remaining items are docs + final bump._

### 10.6 Documentation (12 todo rules across bronze/silver/gold)

All `docs-*` rules require content in the external `home-assistant.io` docs
repo (not this codebase). They block bumping `quality_scale` in `manifest.json`.

#### Bronze docs
- [ ] `docs-high-level-description` — write integration overview
- [ ] `docs-installation-instructions` — config flow walkthrough with screenshots
- [ ] `docs-removal-instructions` — how to remove the integration

#### Silver docs
- [ ] `docs-configuration-parameters` — document options flow parameters
- [ ] `docs-installation-parameters` — document config flow fields (serial port,
  IP, port)

#### Gold docs
- [ ] `docs-data-update` — explain adaptive polling (1s active / 5s idle) and
  metadata refresh (5 min)
- [ ] `docs-examples` — automation examples (e.g., "change ratio when movie
  starts")
- [ ] `docs-known-limitations` — document single controller per entry, no
  passive discovery, serial port platform constraints
- [ ] `docs-supported-devices` — list Seymour masking screen models and Global
  Caché IP2SL adapters
- [ ] `docs-supported-functions` — cover open/close/stop/position, ratio
  presets, diagnostics, calibration
- [ ] `docs-troubleshooting` — connection failures, repair issues, serial port
  permissions
- [ ] `docs-use-cases` — home theater masking screen automation

### 10.7 Final quality scale bump

Once **all** rules at every tier are `done` or `exempt`:

- [ ] Change `manifest.json` → `"quality_scale": "platinum"`
- [ ] Run `python -m script.hassfest` to validate

---

## Out of scope (future work)

- **Brand file** — `homeassistant/brands/seymour_masking_screen.json` may be
  needed if the integration is accepted upstream; verify with hassfest
- **User docs** — external to this repo; write for `home-assistant.io` docs repo
