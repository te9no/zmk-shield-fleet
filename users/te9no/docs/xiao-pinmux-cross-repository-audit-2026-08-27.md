# XIAO BLE pinmux cross-repository audit

Date: 2026-08-27

This audit checks whether ZMK 0.4 firmware selects the ZMK-qualified XIAO BLE board and whether unused connector peripherals remain enabled after shield overlays are applied. It is a source and generated-Devicetree audit; it does not itself authorize firmware changes or pull requests.

## Why this is tracked

The Zephyr XIAO BLE board enables connector peripherals with these default pins:

| Node | Pins |
| --- | --- |
| `xiao_serial` | P1.11 TX, P1.12 RX |
| `xiao_spi` | P1.13 SCK, P1.14 MISO, P1.15 MOSI |
| `xiao_i2c` | P0.04 SDA, P0.05 SCL |

`xiao_ble//zmk` supplies the ZMK board variant and releases the default serial pins, but it does not automatically release every SPI and I2C pin. A shield that reuses these pins must disable an unused node or deliberately override and use that controller. A successful build alone does not prove that two enabled nodes do not claim the same physical pins.

## Trigger and validated pattern

Cornix/Madula commit [`0ed7388`](https://github.com/te9no/zmk-keyboard-cornix/commit/0ed7388847b2b896d260770b58542617a5a619fc) is the trigger.

It applies the reusable sequence:

1. Select `xiao_ble//zmk` for the Madula Trackball, TrackPoint, and IQS targets.
2. Override the board-provided battery node with Madula's A0, 1 MΩ/1 MΩ divider and remove the board power GPIO.
3. Disable unused `xiao_serial`, `xiao_spi`, and `xiao_i2c` nodes in the common shield overlay.
4. Let only the selected module snippet enable its dedicated `spi0` or `i2c0` controller.
5. Inspect the generated DTS and run pristine builds for all affected variants.

The generated Madula Trackball DTS reports all three XIAO connector nodes as disabled. Trackball, TrackPoint, and IQS pristine builds passed 3/3. Hardware CDC diagnostics for Trackball reported Product ID `0x3e`, Revision `0x01`, `ready=true`, and `init_err=0`. The owner then confirmed real pointer/module-input operation. Madula is an integrated Central target, so split relay is not applicable; frame capture and the DYA Studio UI remain unverified.

## Fleet findings

| Repository | Priority | Result | Required follow-up |
| --- | --- | --- | --- |
| Cornix Madula | Applied | Three module targets are qualified; unused connector nodes are disabled; build 3/3, PMW init, and real pointer/module-input passed. | Confirm frame capture and DYA Studio UI. |
| Cornix TPS43 | P0 | Production and host-bond-reset still use bare `xiao_ble`. TPS43 uses P0.05 for its dedicated I2C clock and P0.04 for reset while default `xiao_i2c` also claims P0.04/P0.05. | Apply the Madula qualifier/battery/pin-release pattern and rebuild both variants. Qualify the Central settings-reset target as well. |
| Polaris | P0 | All ZMK 0.4 targets are qualified, but generated DTS keeps `xiao_spi` and `xiao_i2c` enabled. Left OLED uses P1.14/P1.15; right modules reuse P1.13, P0.05, and P0.04. | Disable unused `xiao_spi` in the base and unused `xiao_i2c` on affected right targets; re-enable only an intentionally used controller. |
| MKB2 | P0 | All targets are qualified, but generated DTS keeps `xiao_spi` enabled. OLED always uses P1.14/P1.15, while TB, encoder, and LPPS variants also use P1.13. | Disable unused `xiao_spi` in both base shields and rebuild the full matrix. Keep the deliberately overridden OLED I2C controller. |
| Solstice | P0 | All four US/JIS targets are qualified and serial is disabled. Both key matrices use D8-D10/P1.13-P1.15 while default `xiao_spi` remains enabled. | Disable `xiao_spi` in both base shields and rebuild US/JIS left/right plus settings-reset. |
| SAA | P0 | All dedicated ZMK 0.4 targets are qualified. Default `xiao_i2c` conflicts with common LED power P0.04 and matrix P0.05. Default `xiao_spi` conflicts with encoder, trackpad, and IQS pins; Trackball alone deliberately overrides SPI2. | Disable both connector nodes in the base, then re-enable the required controller only in TB/IQS/TPD overlays. Rebuild all 21 targets on the dedicated branch. |
| Mopolia | Not applicable | Both targets are qualified, UART is disabled, and SPI2 is deliberately overridden for MLX90393. P0.04/P0.05 are unused by the shield. | No source change. Recheck generated DTS when ZMK or module revisions change. |
| Sparagmos | P3 | The stable branch still uses ZMK 0.3 and `seeeduino_xiao_ble`. | Treat this audit as a gate for a future non-default ZMK 0.4 migration branch; do not change stable `master`. |

## Source evidence

- Cornix: `build.yaml`, `boards/shields/madula_central/madula_central.overlay`, and `boards/shields/cornix_tps43_central/cornix_tps43_central.overlay` at `0ed7388`.
- Polaris: `boards/shields/GeaconPolaris/Polaris_pins.dtsi`, `Polaris_L_Base.overlay`, and `snippets/TB_R/TB_R.overlay` on `zmk-0.4`.
- MKB2: `boards/shields/MKB/MKB_{L,R}_Base.overlay`, `MKB_pinctrl_{L,R}.dtsi`, and module overlays on `zmk-0.4`.
- Solstice: `boards/shields/GeaconSolstice/Solstice_{L,R}.overlay` and pinctrl files on `zmk-0.4`.
- SAA: `boards/shields/SparAkashaAnanta/SAA_pins.dtsi`, `SAA_led.dtsi`, module overlays, and `snippets/IQS/IQS.overlay` on `zmk-0.4_validation_cormoran-zmk`.
- Mopolia: `boards/shields/geaconmopolia/geaconmopolia.dtsi` and `geaconmopolia_mlx90393.dtsi` on `main`.

Generated DTS evidence was inspected for Madula, Polaris, and MKB2 from their `just.sh` profiles. Solstice, SAA, Mopolia, and Sparagmos retain a generated-DTS gate in the ledger until a current pristine build is inspected.

## Completion rule

A repository is complete only when every affected build target uses the intended board qualifier, unused connector nodes are disabled in generated DTS, intended module controllers are enabled on the correct pins, pristine builds pass, and representative hardware input still works. Compile success without generated-DTS inspection is insufficient.
