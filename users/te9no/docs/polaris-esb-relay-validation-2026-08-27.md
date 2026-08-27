# Polaris: ESB / DYA Studio relay candidate (2026-08-27)

## Current state

Implementation, local build verification, and a matched-pair flash are complete.
**Hardware/RPC acceptance remains pending.** Do not transfer historical CDC or
input results from the previously installed firmware to this candidate.

| Source | Revision / branch |
| --- | --- |
| Polaris firmware source | [`64860dd`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/64860dde60bf7b20d35bfec0d3d5f61925141be9), `codex/zmk-0.4-esb-validation` |
| Pinned compiled ESB module | [`656477c`](https://github.com/te9no/zmk-feature-split-esb/commit/656477caa56d8909ac78e024cbd943caa6aaa7d7), `codex/esb-cormoran-relay` |
| ESB documentation follow-up | `26ea77246fbc8eb4043cc99e09dde0009a51b1d2` (no production code change) |
| ZMK | Cormoran `e5c9b6915b56801193e359dd9bad4a167ce0d1b8`, unchanged |
| Previously recorded installed pair | `72801a6` + upstream ESB `314c7cb` (historical) |
| Current installed pair | `64860dd` + ESB `656477c`, flashed 2026-08-27 20:32 JST |

Only the owner's fork/experimental firmware branch were published. No upstream
PR or firmware stable/maintenance merge was performed.

## What changed

- ESB now carries Cormoran `RELAY_EVENT` requests and replies, using fragments
  that fit the existing 48-byte radio payload. Transfer ID, total length and
  offset prevent mixed old/new replies. Reassembly is bounded and expires
  after 500 ms of inactivity.
- Both halves enable PMW and custom-settings relay plus core settings-RPC.
  The left USB central enables the PMW custom Studio subsystem. The right is
  underlying ESB source 0, exposed by Cormoran as public Studio source 1.
- Queued frame identity/pipe, queue-full retention and callback recovery are
  checked; complete fragment batches are enqueued atomically.
- Both CDC Debug ports report aggregate reassembled relay receipt counts at
  most once per five seconds. The observer does not log payloads, setting
  values, event names or key values. Existing INFO/privacy cap is retained.
- NCS, sensor driver, GPIO three-wire driver, ADC/battery and pin configuration
  remain unchanged. The earlier PMW initialization failure is a separate gate.

## Evidence

- **96 host ASan/UBSan cases passed**, independently rerun/reviewed. Coverage
  includes the real serializers, both role receive dispatch paths, 240-byte
  payloads, 4/32-byte name limits, malformed/reordered/stale/expired fragments,
  48-byte frame boundaries, queue-full retry, and 100 inline completions.
  These execute extracted C functions with platform stubs, not radio emulation.
- An independent boundary harness exercised 50,000 malformed fragment fixtures
  at each tested name limit without sanitizer findings. This is a local
  additional check, not the CI test count or proof of RF robustness.
- [ESB fork CI](https://github.com/te9no/zmk-feature-split-esb/actions/runs/33066224904)
  passed, including the four upstream negative-control defects.
- The workspace `just.sh` was used via its existing Docker adapter. Committed
  Polaris source `64860dd`: `build-fast ESB --pristine=always`, **2/2 passed**.
  Profile `polaris-esb-validation`, log `build-parallel-20260827-111118`.
- The public fork SHA was explicitly fetched from the owner's repository;
  compiled module checkout was clean and matched the manifest.
- **133 generated-artifact assertions passed**: DTS, Kconfig, linked RPC
  handlers, CDC assignments, GPIO/ADC retention, INFO/no DBG payload strings,
  and exported UF2 hashes. Audit source is
  [`scripts/audit-esb-relay.py`](https://github.com/te9no/zmk-config-GeaconPolaris/blob/64860dde60bf7b20d35bfec0d3d5f61925141be9/scripts/audit-esb-relay.py).
- [Firmware CI](https://github.com/te9no/zmk-config-GeaconPolaris/actions/runs/33066366370)
  completed successfully for head `64860dd`; ledger CI state tracks this run only.

| Artifact | UF2 bytes | SHA256 (local build) |
| --- | ---: | --- |
| `Polaris_L_JOY_ESB_USB` | 799232 | `54d6e10f63ed9160f8f2742464510f420cd1e3e9575d7308f2f3c801ba0c57d2` |
| `Polaris_R_TB_ESB` | 313856 | `63f645422954744fde507aa50e7355248b3e7b523f7608614b58b302fe82cfa5` |

Static RAM use: left 191504/262144 bytes (73.05%); right 107024 bytes (40.83%).
This is not a runtime stack high-water or power measurement.

## Hardware flash and boot evidence

At **2026-08-27 20:32 JST**, the flash-tool transcript records complete copies
of the matching UF2 pair to the identified Polaris halves. The saved CDC boot
logs are `hardware-esb-relay-64860dd-left-flash.log` and
`hardware-esb-relay-64860dd-right-flash.log`; their SHA-256 digests are,
respectively, `861c0fe908842fa87ad22264b161bccf55d18fd42b63b0c2db02cc95bb570b3b`
(3574 bytes) and
`6bd87af89fe259cbadd6f190d5e24f20c9d250294726bc6fdbc587bd91f0aa5b` (2674
bytes). The boot logs record:

| Half | Boot/CDC evidence | Scoped result |
| --- | --- | --- |
| Left JOY USB central | `COM326` at 1200 baud → boot serial `7192CB7FFA85E5D1` → `DebugCOM325`; JOY ready at 100 Hz / 8 ms, ADC2/3, USB configured and Endpoint USB | Flash and CDC boot passed. This is not a physical joystick-input or OLED result. |
| Right TB ESB peripheral | `COM327` at 1200 baud → boot serial `07410F37C96F9FEF` → `DebugCOM327`; PMW3610 initialized at step 3, CPI 800, with no previous PID error | Flash, CDC boot, and sensor initialization passed for **64860dd only**. This does not establish why the historical revision failed or that the relay changed sensor behavior. |

The subsequent 20-second idle captures for both halves had no lines and showed
no fatal error in that limited window. They do not prove ESB connectivity,
runtime relay privacy, RPC success, physical input, or link-loss handling.

## Native local Studio RPC evidence

On 2026-08-27, a read-only native `System.IO.Ports` probe opened left Studio
`COM326` at 12500 baud with DTR and RTS true; no UI was used. The local
enumeration request `AB0801A206020A00AD` succeeded and listed custom subsystem
`cormoran__pmw3610`, index 0. This establishes local USB Studio enumeration and
request acceptance only.

The probe then sent the source 1 GetInfo request
`AB0802A2060A1208080012040A020801AD` and immediately received
`AB0A0D0802A20608120612044A020801AD`: deferred response, request ID 1. No
Peripheral response arrived in the following eight seconds. At 20:39:04 JST,
request 3 (`AB0803A2060A1208080012040A020801AD`) produced
`AB0A0D0803A20608120612044A020802AD` (deferred ID 2), again with no Peripheral
response in eight seconds. At 20:40:36 JST, request 4
(`AB0804A2060A1208080012040A020801AD`) produced
`AB0A0D0804A20608120612044A020803AD` (deferred ID 3), also followed by eight
seconds without a Peripheral response. Concurrent `COM325` and `COM327` Debug
captures at 115200 had no output, including no relay receive counts; on the
third probe DTR and RTS were explicitly asserted on both Debug ports as well as
the Studio port, with the same result. The two earlier probes had DTR/RTS only
on the Studio port, so the third result does not support a DTR explanation. All
ports were closed after the probes.

Therefore **local Studio enumeration/request acceptance passed**, but the
**relay RPC round-trip failed** on `64860dd`. This observation does not prove
ESB connectivity, identify a delivery/receive cause, or change the passed
right-sensor initialization result. Input, stream, reconnect and link-loss
checks remain pending.

## Remaining hardware gates and limits

1. Diagnose ESB delivery and receive handling for the failed source 1 GetInfo
   request, preserving the exact revision and without blindly reflashing the
   unchanged UF2 or assuming a
   cause. Add payload-free ESB TX/RX/ACK/error counters to localize loss; do
   not enable blanket debug logging or key-stroke payload logging. Do not treat
   a UI retry alone as confirmation.
2. After a successful round-trip, verify a reversible, nonpersistent setting
   round-trip and restore its value;
   exercise harmless keys and pointer alongside RPC. No password input.
3. Test timeout with the right disconnected, then reconnect and repeat the
   request. Do not use the `ALL_CONNECTED` icon as live-link evidence.

There is no encryption/authentication or live disconnect detection, and no
automatic stream-stop guarantee. Continuous image streaming is a separate
unaccepted gate. BLE coexistence, nRF53, multiple peripherals/pipe aliasing,
watchdog providers and every generic custom-settings UI operation are not
claimed supported by this one-peer trial.

Previous installed firmware results remain in the
[historical trial report](polaris-esb-usb-only-validation-2026-08-27.md).
