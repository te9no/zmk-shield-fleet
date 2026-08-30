# Cornix / Madula CDC audit — 2026-08-30

Scope: `cdc-acm-zephyr-4.1`, Cornix only, next action
`cornix-madula-1200-baud`. The initial request prohibited flashing. After the
installed LPPS firmware was identified, the owner clarified that switching to
TB firmware was part of this check and authorized that work. Only the verified
main/TB artifact was flashed. No source edits, merges, PRs, or settings resets
were performed.

## Current source and build

Current Cornix [main is 578c9f1](https://github.com/te9no/zmk-keyboard-cornix/commit/578c9f1f94c1a3d2bdd0b7c33ba2fe02c58dac72).
The ledger's `794987c` identifies the earlier CDC integration, not the currently
connected device's firmware. The unrelated local feature-branch checkout was
not used as main evidence and was not changed.

- `config/west.yml` pins cormoran ZMK to `e5c9b6915b56801193e359dd9bad4a167ce0d1b8`.
- Madula TB includes `zmk-usb-logging` and `cornix-cdc-boot`.
- The boot snippet enables the DTE-rate callback, retention boot mode, and
  100 ms delayed CDC bootloader trigger.
- [CI 33278783894](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33278783894)
  completed successfully for all 12 build targets at `578c9f1`.
- [Madula TB job 99170396006](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33278783894/job/99170396006)
  explicitly reports Zephyr 4.1.0. Its generated `.config` and DTS passed
  **19 assertions**: qualified XIAO board, callback/trigger/retention flags,
  delay, enabled and separate Studio/logging CDC devices, and the trigger and
  console both referencing `snippet_zmk_usb_logging_uart`.

No new local build was run. This build result is CI evidence, not a new
`just.sh` result. The subsequent authorized flash is recorded below.

## Initial hardware audit: LPPS firmware with a TB module

The owner reported attaching a TB module to Madula. Windows identified the
same Madula USB device behind COM445 (Studio) and COM447 (logging). COM447
opened at 115200 baud without transmitting a payload; no permitted diagnostic
lines were captured during the initial 12-second read.

The audit then opened **only the identity-checked Madula COM447 at 1200 baud**.
Within approximately one second the device entered bootloader mode:

- H: `XIAO-SENSE`, bootloader CDC COM446.
- UF2 bootloader 0.6.1; model Seeed XIAO nRF52840.
- No firmware or settings were written.

Readback revealed that the installed application was **LPPS, not TB**. All
**1248/1248 application blocks** matched the saved
`codex-madula-lpps-pinout/madula_trackpoint.uf2`, SHA-256
`15e79ee5814df791c2ea709945c4d5500ed09c96e87ffd12aef7bffab3b0b088`.
This hash is already tied to source `81644c2` in the
[LPPS validation record](./madula-lpps-pinout-validation-2026-08-27.md).
It did not match the current-main TB CI artifact, SHA-256
`33d217244e1352f9f07211a53a8330ce9c8e1618aaf014769ca4f47e942f715d`.

Therefore the observed 1200-baud entry is an **LPPS result only**. Attaching a
TB module does not change the flashed firmware variant. It is not evidence
that the main/TB 1200-baud gate passed.

## Authorized TB flash and 1200-baud verification

The main/TB CI artifact above was checked for nRF52840 UF2 family, unique
application blocks, and address range `0x27000..0x96700`. Its SHA-256 was checked
again before writing to the identity-checked Madula bootloader disk. No
bootloader, SoftDevice, or settings-reset artifact was used.

After flashing, Madula enumerated **three CDC ports**. The current-main DTS
contains the board CDC, the Studio CDC, and the logging CDC; the old LPPS port
mapping must not be reused:

| Port | Observation in the TB build |
| --- | --- |
| COM445 | Board CDC interface, not the boot-trigger target |
| COM447 | Studio CDC interface; a 1200-baud request did not enter bootloader |
| COM454 | Logging/boot-trigger CDC; 1200 baud entered bootloader |

The identity-checked **COM454 at 1200 baud** entered H: `XIAO-SENSE` / bootloader
COM446 after approximately **850 ms**. Application readback matched the CI
artifact at **1783/1783 blocks**, proving this test used the TB image rather than
the previously installed LPPS image.

The same hash-verified TB artifact was then written again to recover normal
operation. The bootloader volume disappeared, the same Madula returned as
COM445/COM447/COM454, and **COM454 reopened at 115200 baud**. All serial handles
were closed after the check. The device is left running main/TB firmware.

`1200-baud` is now **passed**, and the completed next action is removed. This
result covers TB bootloader entry and runtime CDC recovery; it does not claim
new pointer-input, DYA Studio, or long-duration acceptance. No CDC log text was
captured in the short read windows, so log-content validation is not claimed.
Earlier DYA Studio and IQS results retain their original evidence.

Stable USB identifiers and full device flash readback are not published. The
temporary full-readback copies are removed after comparison; CI logs, extracted
config/DTS, the checker and a hash/block-count summary remain under local
`.zmk-workspace/evidence/cornix-madula-cdc-audit-20260830/`.
