# Polaris ESB USB-only validation

Date: 2026-08-27

This is a **Polaris-only experiment**, not rollout approval for other keyboards.
The latest built candidate is `3b7cc78` with the public fixed ESB fork `58c8f91`:
87 host cases, pristine 2/2 and 115 audit assertions passed. It was **not flashed**.
Both connected halves still run the previous `72801a6` / upstream `314c7cb` pair;
their earlier CDC success and right-PMW failure are preserved below, not assigned
to the new candidate. This is a functional trial, not a 1 ms latency or
power-consumption measurement.

## Follow-up: public-fork fixes — built, not flashed

The owner requested fixes for four source-level defects and publication in the
public `te9no/zmk-feature-split-esb` fork, followed by a Polaris build. The fixed
fork is published at
[`58c8f912dae87b8197c4d6229e3f2df8cc52daaf`](https://github.com/te9no/zmk-feature-split-esb/commit/58c8f912dae87b8197c4d6229e3f2df8cc52daaf).
Polaris candidate
[`3b7cc78b99c6f1ed76b4349e8c75560b81fb63db`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/3b7cc78b99c6f1ed76b4349e8c75560b81fb63db)
is pushed to `codex/zmk-0.4-esb-validation`. Its source changes from `72801a6` are the
ESB manifest URL/SHA and documentation; firmware maintenance/stable branches are
unchanged.

This follow-up does **not** flash hardware. Both connected halves remain on
Polaris `72801a643a640d2db6b0955b5b9d7b7cd6ddf446` with upstream ESB
`314c7cbaf4a74e1add1d6ffc8249de3e29965b8c`. Its earlier flash/CDC success and
right-TB failure below are historical evidence for that version, not results
for the fork-based build. The new build's flash, CDC, input, sensor
and hardware gates must remain pending until that exact build is tested.

### Source findings and host regressions

The review used the pinned upstream function bodies with host C stubs. Radio,
FIFO, scheduler/queue primitives and injected initialization errors were mocked.
It demonstrates source-level defects, not occurrence on Polaris, RF reliability
or successful hardware behavior. The review covers the nRF52840 USB-only path;
it is not a complete nRF53/MPSL audit.

| Defect | Original host observation | Required regression scope |
| --- | --- | --- |
| In-flight retry identity overwritten by enqueue | A was transmitting, B was queued, and A's failure retried B/decremented B's record instead of A. | Keep payload and retry metadata together, select the in-flight identity at actual transmission, and test overlapping queue/completion behavior. |
| Incomplete RX frame can spin the worker | A 13-byte buffer declared a 19-byte frame; `-EAGAIN` consumed nothing and the worker did not return within the host timeout. | Exit/yield on incomplete input and verify finite progress/recovery for both receive roles. |
| Small valid commands remain pending | One CRC-correct 12-byte layout command stayed buffered although the parser accepted it directly; the threshold included local-only TX metadata. | Use the wire-frame minimum and cover layout, HID-indicator and POLL command sizes, not just changing `>` to `>=`. |
| Radio-enable failure hidden as init success | An injected `-EIO` from enable produced outer init result 0. | Propagate enable failure and avoid announcing transport availability on failure. |

The fixed fork passed **87 host cases with ASan/UBSan**, while all four original
negative demonstrations were detected against upstream `314c7cb`. Coverage also
includes rejecting short malformed payloads by message type, retry order
`A, A, B` and queue-full behavior. The four host gates are passed, and
[fork CI run 33058361591](https://github.com/te9no/zmk-feature-split-esb/actions/runs/33058361591)
completed successfully. Neither result is hardware or RF validation.

These four fixes do not themselves resolve constant `ALL_CONNECTED`, authenticated or
encrypted transport, Cormoran remote RPC support, or the local PMW PID `0x00`
failure. Firmware/debug observations did not demonstrate these four failure
paths occurring on Polaris. No upstream PR is authorized or created by this
follow-up; other keyboards remain outside its scope.

### Fork-based Polaris build evidence

The unchanged workspace `just.sh` ran `update`, confirmed retrieval of the
public fork, then ran `build-fast ESB --pristine=always`: **2/2 targets passed**.
The local build evidence is identified by `build-parallel-20260827-092513`.
`check-esb-fork.py` passed **115 assertions**: the prior 112 plus fork URL,
actual dependency checkout SHA and clean-checkout checks. This verifies the
ESB-only target matrix, declared dependency source and generated DTS/config/
binary expectations for the new candidate, not its runtime behavior.

An independent rerun also passed all 115 checks. Both ELFs contain
`m_current_tx`, `m_retry_pending` and `m_tx_in_flight`, with the old retry table
absent. Ninja's compilation sources resolve to the public fork checkout at
`58c8f912dae87b8197c4d6229e3f2df8cc52daaf`, and the output hashes match below.

| Candidate 3b7cc78 target | UF2 bytes | UF2 SHA-256 |
| --- | ---: | --- |
| Left JOY USB Central | 763,904 | `82e58e585e899d1c8ed5590911ef2fa7553b4c32b2ba4acb44489bbd8bd8726e` |
| Right TB ESB Peripheral | 256,000 | `cff7d2e0a12e0dc302a5c52f59aad2efed60611acdad2d38649b00f0b251b2e9` |

[Polaris CI run 33058405841](https://github.com/te9no/zmk-config-GeaconPolaris/actions/runs/33058405841)
is in progress and recorded as pending, separately from the local 2/2 success
and the fork's successful host-test CI.

No artifact from this table was flashed. All new-candidate hardware gates are
pending, including CDC startup, runtime DEBUG suppression, PMW initialization,
USB/ESB input, reconnection, JOY motion and OLED appearance. The source/binary
logging-cap checks passed within the 115 assertions (`log-privacy-cap`). A
separate `log-privacy-runtime` gate remains pending for this exact candidate.
The previous PMW
failure is not erased: it remains a failed observation for the still-installed
`72801a6`, not a test of candidate `3b7cc78`.

The following sections preserve the prior upstream-driver trial. Their passed
build/flash/CDC and failed sensor results must not be promoted to the new fork
candidate. There is no upstream PR, cross-keyboard rollout or new flash in this
follow-up.

## Historical source and roles — 72801a6

| Component | Revision or role |
| --- | --- |
| Polaris source base | [`84217286bbc5d064b1d6a3e3b3f671017e687942`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/84217286bbc5d064b1d6a3e3b3f671017e687942), the XIAO validation source, not proof that its hardware gates passed |
| Previously flashed Polaris | [`72801a643a640d2db6b0955b5b9d7b7cd6ddf446`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/72801a643a640d2db6b0955b5b9d7b7cd6ddf446); still installed, not the newest candidate |
| Left | JOY, USB-connected Central, ESB receiver |
| Right | TB, ESB Peripheral; CDC Debug remains a separate diagnostic path |
| ESB module | [`badjeff/zmk-feature-split-esb@314c7cbaf4a74e1add1d6ffc8249de3e29965b8c`](https://github.com/badjeff/zmk-feature-split-esb/commit/314c7cbaf4a74e1add1d6ffc8249de3e29965b8c) |
| NCS compatibility dependency | `badjeff/sdk-nrf@9b3d2623fdcd9c0fd0284f860beea924568c9826` |
| nrfxlib | `nrfconnect/sdk-nrfxlib@dfadf17305d8f000eda9aa74a5b9ff1c5647a23e` |
| ZMK core, unchanged | `cormoran/zmk@e5c9b6915b56801193e359dd9bad4a167ce0d1b8` |

The earlier ESB builds used these source pins, verified by the independent audit along
with the two-target matrix and generated DTS/config. The module source SHA must
not be mistaken for a Polaris implementation commit. At this earlier stage the
keyboard tracking commit was `72801a6`; current tracking now identifies the
unflashed `3b7cc78` candidate described above. No firmware PR or merge was made,
and firmware `main` / `zmk-0.4` remain unchanged.

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
`ea2ca2c60a0d0696633bf6169db0cd875e39d783`. They do not identify the later
`72801a6` logging-cap build or the new `3b7cc78` fork candidate.
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

## Historical validation checklist — 72801a6

Targeted build, source/pin/matrix/DTS/config audit, flash, CDC and the logging cap
passed for `72801a6`. Its CI was pending at that earlier recording. The right sensor-init gate failed;
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

## Still-installed firmware — source 72801a6

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
using no confidential input, during the earlier capture. No key-counter
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

## Previous trial status — 72801a6

- Both current halves: `72801a643a640d2db6b0955b5b9d7b7cd6ddf446`; early `ea2ca2c` retained as history.
- Per-side pristine builds, two-target/source/pin/DTS/config audit and 112 assertions: passed.
- Earlier `72801a6` reflash, CDC startup and global DEBUG cap: passed. Right PMW initialization: failed.
- CI run 33045609894 was pending when this previous-trial record was made; it is not the new candidate's CI.
- Actual ESB receipt, key/pointer transfer, reconnection, JOY movement and OLED appearance: pending.
- Latency and power consumption: not measured; do not claim 1 ms performance.
- No firmware promotion, external PR or cross-keyboard rollout is authorized by
  this record. The experiment remains on its dedicated branch.
