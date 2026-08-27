# Polaris ESB USB-only validation

Date: 2026-08-27

This is a **Polaris-only experiment**, requested by the owner while Polaris is
connected. It is not a rollout approval for other keyboards. Both halves now run
source `72801a6`: `just.sh` pristine 2/2, 112 audit assertions, CDC reflashing and
DEBUG-log suppression passed. Right PMW initialization still fails. ESB receipt,
key/pointer transfer, reconnection, JOY movement and OLED appearance remain
unverified. Earlier `ea2ca2c` observations are retained separately below. This is
a functional trial, not a 1 ms latency or power-consumption measurement.

## Source and roles

| Component | Revision or role |
| --- | --- |
| Polaris source base | [`84217286bbc5d064b1d6a3e3b3f671017e687942`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/84217286bbc5d064b1d6a3e3b3f671017e687942), the XIAO validation source, not proof that its hardware gates passed |
| Polaris experiment | `codex/zmk-0.4-esb-validation`; current source [`72801a643a640d2db6b0955b5b9d7b7cd6ddf446`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/72801a643a640d2db6b0955b5b9d7b7cd6ddf446) |
| Left | JOY, USB-connected Central, ESB receiver |
| Right | TB, ESB Peripheral; CDC Debug remains a separate diagnostic path |
| ESB module | [`badjeff/zmk-feature-split-esb@314c7cbaf4a74e1add1d6ffc8249de3e29965b8c`](https://github.com/badjeff/zmk-feature-split-esb/commit/314c7cbaf4a74e1add1d6ffc8249de3e29965b8c) |
| NCS compatibility dependency | `badjeff/sdk-nrf@9b3d2623fdcd9c0fd0284f860beea924568c9826` |
| nrfxlib | `nrfconnect/sdk-nrfxlib@dfadf17305d8f000eda9aa74a5b9ff1c5647a23e` |
| ZMK core, unchanged | `cormoran/zmk@e5c9b6915b56801193e359dd9bad4a167ce0d1b8` |

The ESB builds use these source pins, verified by the independent audit along
with the two-target matrix and generated DTS/config. The module source SHA must
not be mistaken for a Polaris implementation commit. The keyboard tracking
commit identifies the current logging-capped version. The dedicated firmware
branch is public at `72801a6`; no firmware PR or merge was made, and firmware
`main` / `zmk-0.4` remain unchanged.

The source adds separate ESB shields/configs and a final snippet. It uses
Peripheral ID 0, one peripheral and a 48-byte payload. Left uses standard OLED
without Bongo and ordinary USB Studio; right retains CDC and the 3-wire
controller. Relay and BLE-management functionality are disabled for ESB. The
settings-RPC module also requires RELAY macros and is disabled only for this ESB
configuration; this does not remove ordinary USB Studio.

The successful builds have left Debug on the board CDC plus a Studio CDC (two
CDC instances) and right Debug (one CDC instance). Both Debug ports returned and
provided startup logs after both flash rounds. Ordinary Studio UI connectivity
has not been demonstrated by this observation. Independent DTS/config auditing
passed for the current version.

## Early build results and BLE isolation

The earlier `ea2ca2c` ESB targets passed pristine builds through `just.sh`:

| Target | FLASH bytes | RAM bytes | UF2 bytes | UF2 SHA-256 |
| --- | ---: | ---: | ---: | --- |
| Left JOY USB Central | 406,564 | 162,496 | 813,568 | `d244521a474abeb0382d62b117f71eacee923b4892d8753051957328860139f7` |
| Right TB ESB Peripheral | 131,816 | 83,632 | 263,680 | `d27a440b208834cb5c3761684d109df71e7376d81aa78a0dcb191d88de0d1b80` |

These hashes identify the initial artifacts flashed from source
`ea2ca2c60a0d0696633bf6169db0cd875e39d783`. They do not identify the forthcoming
logging-cap build. Reconfirm artifact identity before any further flash.
FLASH/RAM figures are build resource sizes, not power or latency measurements.

A normal BLE JOY smoke build using the same ESB/NCS manifest **failed during
CMake generation** because NCS security sources `pk.c`, `platform.c` and
`oberon_helpers.c` were missing. Therefore, the ESB branch's `build.yaml` now
contains **two ESB targets only**, verified by the independent audit. This is
isolation of the experiment, not a successful BLE compatibility test. Do not
claim that all nine normal BLE targets can build on this branch.

Normal BLE firmware must be built from the original `8421728` source or the
maintenance branch with its original profile/dependencies. Those original
branches are unchanged. Keeping their configurations intact is not evidence of
compatibility with the ESB branch's NCS manifest.

## Constraints to review before the hardware trial

- This ESB configuration cannot coexist with BLE. The left Central must connect
  to the PC by USB; this is not a Bluetooth-to-PC test.
- The reviewed ESB module provides no encryption or authentication. CRC and a
  distinct radio address do not provide either property. Limit testing to
  non-sensitive input, and explicitly review this limitation before use. The
  security-review gate remains pending until the trial's review is recorded.
- The module handles its ordinary event types, including input and battery
  events, but does not implement Cormoran's `RELAY_EVENT`. Remote PMW diagnostics
  and custom-settings RPC over the split are unsupported in this experiment.
  Do not treat missing remote Studio features as a newly fixed/failed PMW
  driver result, or mark existing Studio gates passed from this trial.
- `get_status` always reports `ALL_CONNECTED`. A connected label or OLED status
  cannot prove a radio connection. The available instrumentation counts public
  ZMK key events for source 0 over five-second intervals and observes received
  peripheral battery reports. It does not directly count ACKs and must not be
  presented as ACK statistics. Verify actual events, including after a restart.
  The dedicated counters retain counts rather than key values. A separate
  global-debug logging issue found during early flash was capped in `72801a6`,
  with binary checks and both new boot logs confirming DEBUG suppression.
  Continue to restrict input to non-sensitive test actions.
- The existing left Bongo OLED has BLE dependencies. The ESB build selects a
  temporary standard OLED screen for ESB only, not a permanent replacement.
  Its generated configuration and visible result remain unverified.

## Validation checklist

Targeted build, source/pin/matrix/DTS/config audit, flash, CDC and the logging cap
have passed for `72801a6`. CI is pending. The right sensor-init gate failed;
transport and actual input gates remain pending. Associate subsequent results
with the exact commit and per-side artifact hashes, keeping versions apart.

| Gate | Required observation |
| --- | --- |
| Dependency pins / source audit | Passed for the declared ESB/NCS/nrfxlib/cormoran pins and source checks in the independent audit. |
| Targeted build / generated config | `just.sh` pristine 2/2 and 112 source/DTS/config/binary assertions passed. This is local validation, not CI success. |
| CI | Run [33045609894](https://github.com/te9no/zmk-config-GeaconPolaris/actions/runs/33045609894) started and is pending at this record update. |
| BLE target isolation | Verified ESB-only two-target matrix; normal BLE uses the original branch/profile. The failed same-manifest BLE smoke test remains historical evidence. |
| Left/right flash | Both sides were reflashed and booted on `72801a6`; early `ea2ca2c` is no longer installed. |
| CDC Debug / log privacy cap | Both current Debug boot logs returned and contained no DBG output. MAX/OVERRIDE, missing binary DBG strings and retained INFO messages were audited. |
| USB host / ESB key input | Confirm local left key reports and actual right key reports reach the USB host through the left Central. |
| ESB connectivity / reconnect | Observe source-0 public key-event counts and received peripheral battery reports, then repeat after peripheral restart. Constant connection status is insufficient, and no direct ACK count is available. |
| Left JOY | Confirm direction, speed and sustained input independently of ESB transport. |
| Right TB sensor init | Obtain valid sensor identity/readiness before claiming a successful pointer test; keep earlier PMW failure history intact. |
| ESB pointer relay | Verify valid right-TB input reaches the host via ESB, separately from sensor initialization and key-event transfer. |
| OLED trial display | Confirm the chosen ESB-only display boots and renders as expected; do not claim Bongo functionality unless observed. |
| Overall hardware | All required gates and both variants must be resolved; partial transport success does not complete the experiment. |

## Current firmware — source 72801a6

The only code change from `ea2ca2c` is `CONFIG_LOG_MAX_LEVEL=3`; the accompanying
validation documentation was updated. Both targets were rebuilt pristine through
`just.sh`. The audit passed **112 assertions**: the original 97, four MAX/OVERRIDE
checks, eight checks for absent binary DEBUG strings, and three checks retaining
INFO diagnostics.

| Target | UF2 bytes | UF2 SHA-256 |
| --- | ---: | --- |
| Left JOY USB Central | 764,416 | `1466087130461fbc14152dc3537beb4c55cba56a22a79922caf791d644c5d74a` |
| Right TB ESB Peripheral | 256,512 | `05256070eb1d51db21ac9ce863fbb6d2c12f86a5d28fd5be098889460eae07e8` |

Both artifacts were reflashed using CDC: left COM326 → H → Debug COM325, and
right COM327 → I → COM327. Left again reported JOY initialization ready at
100 Hz / 8 ms report interval and USB endpoint selection. Right booted, then
repeated the PMW Product ID `0x00` initialization failure after 11 attempts.
Both new boot logs contained **zero DBG messages**. These observations pass the
flash/CDC/logging-cap gates, not actual JOY movement or USB host input.

Actual ESB receive counters, key input, pointer relay and reconnection remain
pending. The owner has been asked to press right-side letter keys a few times
using no confidential input, while capture is in progress. No key-counter
reception or user result has yet been recorded. OLED appearance also awaits
visual confirmation. Current firmware on **both** halves is `72801a6`, not the
earlier XIAO or comparison-baseline pair.

## Early flash — source ea2ca2c

The following observations belong only to source
`ea2ca2c60a0d0696633bf6169db0cd875e39d783` and the two UF2 hashes above:

| Side | Observed flash and startup | Interpretation |
| --- | --- | --- |
| Left JOY | Studio COM326 at 1200 baud → H bootloader → Debug COM325. JOY initialization reported ready, 100 Hz sampling, 8 ms report interval and ADC channels 2/3. USB endpoint was selected. | Flash and CDC startup passed. Initialization and endpoint selection do not prove JOY movement or host key input. |
| Right TB | Debug COM327 at 1200 baud → I bootloader → COM327. PMW Product ID was `0x00`, expected `0x3e`; initialization failed at step 2 after 11 attempts. | Flash and CDC startup passed; sensor initialization failed. This repeats the earlier symptom but does not diagnose its cause. |

ESB HF-clock startup was observed. No actual receive-counter or peripheral
battery event was observed in this initial capture; both sides reported ADC
`0 mV` / `0%` with no change. This does not prove radio connectivity, nor does it
establish an ESB failure. Connectivity, received key events and pointer relay
remain **pending** until actual functional evidence is available.

The initial firmware also emitted global DEBUG logs because USB logging resulted
in `CONFIG_ZMK_LOG_LEVEL=4`. At that stage a `CONFIG_LOG_MAX_LEVEL=3` cap was planned
and had no completed replacement artifact or privacy-cap check. The subsequent
`72801a6` build, reflash and cap verification are recorded above; this paragraph
preserves the initial observation rather than describing the current firmware.

## Existing PMW failure is a separate issue

The preceding [pinmux hardware report](polaris-pinmux-hardware-validation-2026-08-27.md)
records right-TB Product ID `0x00`, OBSERVATION `0xff` and initialization failure
on both the new XIAO firmware and the previous distribution firmware. A
successful rollback transfer did not restore the sensor. This is historical
evidence preceding ESB, not an ESB regression diagnosis.

Both halves have since moved through initial ESB firmware to current `72801a6`. The
old report's right-baseline/left-XIAO state describes the comparison period, not
the currently flashed pair. Keep its failed gates and observations as history.
Radio/key events may be tested independently, but neither ESB connectivity nor a
successful build clears the unresolved TB sensor/pointer gate.

Before the ESB flash, the check reconfirmed both connected halves and retained
recovery images. At that time the previous right firmware was still running with
approximately 92 minutes of uptime; that earlier check was not evidence of a
restart or PMW recovery.
Rechecked rollback image SHA-256 values are:

- Left JOY, XIAO validation firmware:
  `43462da128f99c24dc368e60fa4b7f999d98a3c57acdb1f043014c1ae895dcf3`.
- Right TB, previous distribution firmware:
  `2dbb49c0036be7dbf3d2fa94b2137acac471bc646ce35ba779eab31f81186f78`.

These are recovery-image identities, not ESB artifact identities or successful
rollback/flash results for this experiment.

## Current status and remaining checks

- Both current halves: `72801a643a640d2db6b0955b5b9d7b7cd6ddf446`; early `ea2ca2c` retained as history.
- Per-side pristine builds, two-target/source/pin/DTS/config audit and 112 assertions: passed.
- Current reflash, CDC startup and global DEBUG cap: passed. Right PMW initialization: failed.
- CI run 33045609894: pending, separate from successful local builds.
- Actual ESB receipt, key/pointer transfer, reconnection, JOY movement and OLED appearance: pending.
- Latency and power consumption: not measured; do not claim 1 ms performance.
- No firmware promotion, external PR or cross-keyboard rollout is authorized by
  this record. The experiment remains on its dedicated branch.
