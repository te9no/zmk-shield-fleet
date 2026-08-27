# Polaris: ESB / DYA Studio relay candidate (2026-08-27)

## Current state

Implementation and local build verification are complete. **Not flashed;
hardware/RPC acceptance remains pending.** Do not transfer historical CDC or
input results from the previously installed firmware to this candidate.

| Source | Revision / branch |
| --- | --- |
| Polaris firmware source | [`64860dd`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/64860dde60bf7b20d35bfec0d3d5f61925141be9), `codex/zmk-0.4-esb-validation` |
| Pinned compiled ESB module | [`656477c`](https://github.com/te9no/zmk-feature-split-esb/commit/656477caa56d8909ac78e024cbd943caa6aaa7d7), `codex/esb-cormoran-relay` |
| ESB documentation follow-up | `26ea77246fbc8eb4043cc99e09dde0009a51b1d2` (no production code change) |
| ZMK | Cormoran `e5c9b6915b56801193e359dd9bad4a167ce0d1b8`, unchanged |
| Last recorded installed pair | `72801a6` + upstream ESB `314c7cb`, unchanged by this work |

Only the owner's fork/experimental firmware branch were published. No upstream
PR, firmware stable/maintenance merge, or device flash was performed.

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
  is separate from those local results; ledger CI state tracks this run only.

| Artifact | UF2 bytes | SHA256 (local build) |
| --- | ---: | --- |
| `Polaris_L_JOY_ESB_USB` | 799232 | `54d6e10f63ed9160f8f2742464510f420cd1e3e9575d7308f2f3c801ba0c57d2` |
| `Polaris_R_TB_ESB` | 313856 | `63f645422954744fde507aa50e7355248b3e7b523f7608614b58b302fe82cfa5` |

Static RAM use: left 191504/262144 bytes (73.05%); right 107024 bytes (40.83%).
This is not a runtime stack high-water or power measurement.

## Remaining hardware gates and limits

1. On an explicit flash request, install the matching pair and identify their
   CDC ports again. Check right PMW initialization independently.
2. Connect Studio to the left's Studio CDC; request **source 1** GetInfo or
   one-shot diagnostics. Correlate the two Debug receive counters with the
   actual right-hand response. Counts alone do not prove RPC success.
3. Verify a reversible, nonpersistent setting round-trip and restore its value;
   exercise harmless keys and pointer alongside RPC. No password input.
4. Test timeout with the right disconnected, then reconnect and repeat the
   request. Do not use the `ALL_CONNECTED` icon as live-link evidence.

There is no encryption/authentication or live disconnect detection, and no
automatic stream-stop guarantee. Continuous image streaming is a separate
unaccepted gate. BLE coexistence, nRF53, multiple peripherals/pipe aliasing,
watchdog providers and every generic custom-settings UI operation are not
claimed supported by this one-peer trial.

Previous installed firmware results remain in the
[historical trial report](polaris-esb-usb-only-validation-2026-08-27.md).
