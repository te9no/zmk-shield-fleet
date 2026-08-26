# Polaris PMW3610 three-wire validation — 2026-08-26

This record covers only the right-hand Polaris trackball variant. It records
transport and sensor-initialization evidence separately from pointer behavior;
it does not mark physical direction or sensitivity as passed.

## Revisions under test

- Firmware branch: `codex/zmk-0.4-three-wire-spi-module`
- Firmware revision: `30fe2bd63dd254ab0f2c08e5df2ce9387707f787`
- Generic controller: `te9no/zmk-driver-spi-three-wire` `main`
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

These results demonstrate that the generic controller can run the original
cormoran driver on the Polaris P0.05 shared-SDIO wiring without modifying that
driver.

## Pending gates

- Physical pointer direction
- Pointer sensitivity
- Split reconnection and relayed input
- DYA Studio source enumeration and frame capture
- Left-hand Polaris trackball variant

Until those checks pass, the validation branch must not be treated as a
completed hardware rollout or promoted to the stable firmware branch.
