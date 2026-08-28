# MKB pinmux and three-wire validation — 2026-08-28

This records the combined MKB pinmux/three-wire validation branch. Source and
build gates are recorded separately; this is not a firmware release or hardware acceptance.

## Source

- Repository: [te9no/zmk-config-MKB2](https://github.com/te9no/zmk-config-MKB2/tree/codex/zmk-0.4-pinmux-three-wire)
- Branch: `codex/zmk-0.4-pinmux-three-wire`
- Source validation commit: [`03fa08e`](https://github.com/te9no/zmk-config-MKB2/commit/03fa08eb09c0033a229e1fee37da9c0f32b942bd). Automated firmware publication can add an artifact-only commit after this source revision.
- Pinmux source: [`3361c9e`](https://github.com/te9no/zmk-config-MKB2/commit/3361c9e2e40a1d05f88ba47447b4a14050699ad3), based on `zmk-0.4@7b02e9b`.
- The seven three-wire source files from [`8f83136`](https://github.com/te9no/zmk-config-MKB2/commit/8f8313681846ca6db8496a1f239b4acf40c6fa50) were transferred. The VIA branch and generated UF2 artifacts were not transferred; MKB pin-release settings remain.
- Fixed modules: cormoran ZMK core `e5c9b69`, cormoran PMW3610 driver `5c34ea0`, and public three-wire driver `4362133`.
- Wiring verified in generated DTS: TB/TBv4 SCK=P1.13, SDIO=P0.04, CS=P1.12, IRQ=P0.05; TBv3 SCK=P0.05, SDIO=P0.04, CS=P1.12, IRQ=P1.13. D7/D8 map to P1.12/P1.13, not P0.07/P0.08.

## CI

[CI run 33151685626](https://github.com/te9no/zmk-config-MKB2/actions/runs/33151685626) completed successfully at source `03fa08e`: **16/16 targets** (15 keyboard variants and settings reset).

All 16 successful build-job logs were downloaded from this run. Their generated
`zephyr.dts` and `.config` outputs passed **487 assertions**, including:

- `xiao_ble/nrf52840/zmk` generated board qualifier and disabled connector UART/SPI.
- All three TB variants: GPIO three-wire bus, disabled hardware SPI0, exact SCK/SDIO/CS/IRQ pins, CPI800, disabled burst read, settings IDs, and existing input-transform routing.
- All 15 keyboard variants: OLED I2C P1.14/P1.15, Bongo Cat, CDC logging/boot trigger, battery AIN7 and P0.14 power control with 510k/1.51M divider.
- JOY oversampling and ADC2/ADC3, encoder D7/D8, LPPS SPI and TPD/RZT I2C assignments; three-wire disabled in non-TB targets.

The checker was rerun by the supervising agent. Its negative probe against the
old local pinmux build rejects the missing three-wire configuration. Old local
build output was not used as evidence for this source.

Local evidence: `.zmk-workspace/evidence/mkb-pinmux-three-wire-20260828/`
contains `jobs.json`, raw job logs, the extraction/check scripts, 32 extracted
files under `targets/`, and `targets.sha256`.

The workflow published all 16 UF2s in artifact-only commit
[`4234531`](https://github.com/te9no/zmk-config-MKB2/commit/42345317d35727741294453e86852fe4d1ea145b).
Only firmware files differ from source `03fa08e`; source validation and hardware
acceptance are still distinct.

## Local build

`just.sh --profile mkb-xiao-pinmux build-fast all --pristine=always` could not
connect to Docker Desktop and exited before compilation began. The
`local-just-build` gate remains pending; this is an environment blocker, not a
compiler failure. Docker Desktop also failed to start. No Docker reset, cache
deletion, or direct-`west` local substitute build was performed. GitHub CI is a
separate build gate and does not imply that the local `just.sh` check passed.

## Hardware

All hardware gates remain pending. No firmware was flashed and no device or
official-site hardware validation was performed. Existing results from the
3361c9e pinmux branch or 8f83136 three-wire work are not transferred to this
new source revision. Stable and maintenance branches are unchanged; there is
no firmware PR.
