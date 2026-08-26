# Polaris PMW3610 three-wire validation — 2026-08-26

This record covers only the right-hand Polaris trackball variant. It records
transport and sensor-initialization evidence separately from pointer behavior;
it does not mark physical direction or sensitivity as passed.

## Revisions under test

- Firmware branch: `codex/zmk-0.4-three-wire-spi-module`
- Firmware revision: `30fe2bd63dd254ab0f2c08e5df2ce9387707f787`
- Generic controller: `te9no/zmk-driver-spi-three-wire` release `v0.1.0`
- Controller revision: `4362133dbfbf66788b66b0a3e3c410b9232c06cb`
- PMW3610 driver: unchanged
  `cormoran/zmk-driver-pmw3610-with-custom-studio-rpc`
  `5c34ea0eec246a1c986111417cd779b53144629a`

## Passed gates

- `just.sh` built `Polaris_R_MODULE_TB` successfully: FLASH 308260 bytes and
  RAM 120884 bytes.
- Opening `COM327` at 1200 baud with DTR entered the right-hand
  `I:XIAO-BOOT` loader.
- `just.sh` flashed the firmware successfully to the right-hand `I` boot drive.
- The right half returned as CDC `COM327`.
- The three-wire controller reported ready for the Polaris SCK/SDIO wiring.
- Startup transaction diagnostics reported `result=0` throughout the captured
  transfer window.
- PMW3610 self-test observation was `0x7f`; its low nibble was the expected
  `0x0f`.
- Product ID was the expected `0x3e`.
- The PMW3610 driver reported `PMW3610 initialized` with initialization error
  zero.
- A second `just.sh` flash to `I:XIAO-BOOT` returned on `COM327`. Its startup
  trace reported Product ID `0x3e`, OBSERVATION `0x6f` (expected low nibble
  `0x0f`), every logged transfer with `result=0`, and `PMW3610 initialized`.
- The user then confirmed physical pointer input from the right trackball. As
  this half was running as the connected Peripheral, the observed host pointer
  input also validates the right-to-Central split relay path.
- The public `v0.1.0` tag and its remote ref both resolve to controller commit
  `4362133dbfbf66788b66b0a3e3c410b9232c06cb`.
- The release is public and non-draft. Its source archive contains only tracked
  source, binding, fixture, documentation, and license files; no build output,
  Python bytecode, or cache directory is included.
- `tests/verify_build.py` passed against the `just.sh` Polaris right-TB build.

## Renode protocol regression

- Test branch: `te9no/zmk-driver-spi-three-wire`
  `codex/renode-half-duplex`
- Test revision: `a60128717261b7f12a6ec402b1c44a43c3096352`
- The pure Zephyr 4.1 nRF52840 fixture passed both Robot scenarios.
- The normal scenario observed three command bytes, three returned bytes, and
  three shared-SDIO turnarounds. Both the cormoran-style leading-discard read
  and explicit `SPI_HALF_DUPLEX` read returned Product ID `0x3e`; OBSERVATION
  returned `0x0f`.
- The injected constant-`0x3e` fault preserved the apparently valid Product ID
  but made OBSERVATION read `0x3e`, and the fixture detected it explicitly.

This is protocol-level evidence for the unchanged v0.1.0 controller source. It
does not replace hardware checks for voltage levels, signal integrity, timing
margins, pointer behavior, or split transport.

These results demonstrate that the generic controller can run the original
cormoran driver on the Polaris P0.05 shared-SDIO wiring without modifying that
driver.

## Pending gates

- Physical pointer direction and sensitivity
- DYA Studio source enumeration and frame capture
- Left-hand Polaris trackball variant

Until those checks pass, the validation branch must not be treated as a
completed hardware rollout or promoted to the stable firmware branch.
