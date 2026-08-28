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

Cornix/Madula commit [`0ed7388`](https://github.com/te9no/zmk-keyboard-cornix/commit/0ed7388847b2b896d260770b58542617a5a619fc) is the original trigger. The completed reference is Cornix [`main@794987c`](https://github.com/te9no/zmk-keyboard-cornix/commit/794987c0a15c903c107a06db28110f66f75ddda8).

It applies the reusable sequence:

1. Select `xiao_ble//zmk` for the Madula Trackball, TrackPoint, and IQS targets.
2. Override the board-provided battery node with Madula's A0, 1 MΩ/1 MΩ divider and remove the board power GPIO.
3. Disable unused `xiao_serial`, `xiao_spi`, and `xiao_i2c` nodes in the common shield overlay.
4. Let only the selected module snippet enable its dedicated `spi0` or `i2c0` controller.
5. Inspect the generated DTS and run pristine builds for all affected variants.

The generated Madula Trackball DTS reports all three XIAO connector nodes as disabled. The final main integration qualifies the Madula Trackball, TrackPoint, and IQS targets as well as TPS43 production, host-bond-reset, and Central settings-reset. It also releases the unused connector peripherals in both Madula and TPS43 common overlays.

Cornix `just.sh` manifest builds passed 12/12, the `madula-pmw-debug` opt-in build passed, the normal Trackball pristine rebuild passed, and [GitHub Actions run 32991787396](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/32991787396) succeeded. Hardware CDC diagnostics for Trackball reported Product ID `0x3e`, Revision `0x01`, `ready=true`, and `init_err=0`; the owner confirmed real pointer/module-input operation. Madula is an integrated Central target, so split relay is not applicable. PR #3 is closed, remote validation branches `zmk-0.4_validation_pmw3610-cormoran-rpc` and `codex/zmk-0.4-three-wire-spi-module` were deleted, and the maintenance branch `zmk-0.4` was retained.

## Fleet findings

| Repository | Priority | Result | Required follow-up |
| --- | --- | --- | --- |
| Cornix Madula | Complete | Three module targets are qualified; unused connector nodes are disabled; main integration, manifest 12/12, debug opt-in, normal pristine rebuild, CI, PMW init, and real pointer/module-input passed. | None for this pin-release item. |
| Cornix TPS43 | Complete | Production, host-bond-reset, and Central settings-reset are qualified. The common overlay releases unused connector peripherals; main and CI builds passed. | None for this pin-release item. |
| Polaris | P0 / BLE pair restored, hardware incomplete | `8421728` passed build/DTS/CI. The historical `8421728` and hash-verified old-UF2 PMW failures are preserved. By 21:04:23 JST both halves were restored to matched `8421728`; boot, split security callback, right PMW initialization/CPI800, and read-only remote PMW GetInfo RPC passed. | Verify physical left JOY/OLED and right TB input. Do not claim hardware completion from boot, split, sensor initialization, or read RPC. |
| MKB2 | P0 / local build and hardware pending | The former `3361c9e` pinmux result is historical. The [2026-08-28 combined validation](./mkb-pinmux-three-wire-validation-2026-08-28.md) at source `03fa08e` passes CI 16/16 and 487 generated-DTS/config assertions; all three TB variants use the public three-wire module. | Local `just.sh` is blocked by Docker startup; verify it and representative hardware before maintenance integration. |
| Solstice | P0 / hardware pending | Validation branch `643a256` passes `just.sh` pristine 5/5 and 101 generated-DTS/config assertions. Four added overlay lines disable unused SPI while keeping matrix, left OLED/analog, right TB, battery, and CDC configuration. | Verify representative hardware on the new revision before maintenance integration. |
| SAA | Medium / hardware pending | Validation branch `0540667` passes `just.sh` pristine 21/21 and 786 generated-DTS/config assertions for unused-bus release and preserved settings. Existing TPD+IQS pin ownership fails separately in generated DTS. | Verify representative hardware; resolve the separate TPD+IQS wiring/controller conflict before claiming that combination ready. |
| Mopolia | Not applicable | Both targets are qualified, UART is disabled, and SPI2 is deliberately overridden for MLX90393. P0.04/P0.05 are unused by the shield. | No source change. Recheck generated DTS when ZMK or module revisions change. |
| Sparagmos | P3 | The stable branch still uses ZMK 0.3 and `seeeduino_xiao_ble`. | Treat this audit as a gate for a future non-default ZMK 0.4 migration branch; do not change stable `master`. |

### MKB follow-up — 2026-08-28

The new `codex/zmk-0.4-pinmux-three-wire` source at `03fa08e` combines the
3361c9e pin-release base with the historical three-wire source from 8f83136.
The [dedicated validation record](./mkb-pinmux-three-wire-validation-2026-08-28.md)
records the source, CI, local-build, and hardware gates separately. The new CI
run passes 16/16 targets and 487 generated-DTS/config assertions. Local
`just.sh` is blocked before compilation by Docker startup; hardware is pending.
Earlier local-build and hardware results are historical and are not transferred
to this revision.

## Source evidence

- Cornix: `build.yaml`, `boards/shields/madula_central/madula_central.overlay`, and `boards/shields/cornix_tps43_central/cornix_tps43_central.overlay` at `main@794987c`.
- Polaris: `boards/shields/GeaconPolaris/Polaris_pins.dtsi`, `Polaris_L_Base.overlay`, and `snippets/TB_R/TB_R.overlay` on `zmk-0.4`.
- MKB2: `boards/shields/MKB/MKB_{L,R}_Base.overlay`, `MKB_pinctrl_{L,R}.dtsi`, and module overlays on `zmk-0.4`.
- Solstice: `boards/shields/GeaconSolstice/Solstice_{L,R}.overlay` and pinctrl files on `zmk-0.4`.
- SAA: `boards/shields/SparAkashaAnanta/SAA_pins.dtsi`, `SAA_led.dtsi`, module overlays, and `snippets/IQS/IQS.overlay` on `zmk-0.4_validation_cormoran-zmk`.
- Mopolia: `boards/shields/geaconmopolia/geaconmopolia.dtsi` and `geaconmopolia_mlx90393.dtsi` on `main`.

Generated DTS evidence was inspected for Madula, Polaris, MKB2, Solstice, and SAA from their `just.sh` profiles. The four rollout repositories passed 51/51 pristine builds and 1,246 generated-DTS/config assertions in total. All four retain pending hardware gates. The maintenance refs remain at the stated base revisions; no firmware PR or maintenance/stable merge has been performed. Mopolia and Sparagmos retain a generated-DTS gate until a current pristine build is inspected.

## Polaris validation branch

The source changes are pushed as [`8421728`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/84217286bbc5d064b1d6a3e3b3f671017e687942) on `codex/zmk-0.4-xiao-pinmux`, based on maintenance `zmk-0.4@ed5cba4`. Neither maintenance nor stable has been merged, and no PR has been created.

The successful CI subsequently advanced the branch to artifact-publication commit [`a7f3074`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/a7f307497a467bfefa91a6e00392b87447c2af13), whose parent is `8421728` and whose only changes add 9 generated UF2 files. The ledger's source-validation commit intentionally remains `8421728`. Any later maintenance integration must be **source-only**, excluding generated firmware/artifact-publication commits. This rollout does not change the automatic publication workflow.

- `just.sh` pristine builds passed all 9 manifest targets: 8 keyboard variants and settings reset.
- [GitHub Actions run 33037002324](https://github.com/te9no/zmk-config-GeaconPolaris/actions/runs/33037002324) finished successfully, including all 9 build targets and artifact publication.
- Generated DTS and `.config` checks passed 101 assertions. The 8 keyboard variants disable unused UART/SPI; right-side I2C is disabled, and left OLED I2C1 remains enabled.
- Battery sensing keeps Polaris's A0, 470 kΩ/1.47 MΩ divider and NiMH thresholds. The inherited board power GPIO is removed with a property deletion, not replaced by an empty GPIO property.
- JOY oversampling, CDC, cormoran ZMK, Bongo Cat, and the existing 3-wire transport remain configured.
- Historical `8421728` and old-UF2 comparisons recorded PMW3610 initialization failures. A subsequent normal-BLE restore returned both halves to matched `8421728`; right PMW initialization/CPI800, split security callback, and read-only remote PMW GetInfo RPC passed. These new observations do not erase the failures or prove physical pointer/JOY input or OLED behavior. See the [2026-08-27 hardware comparison](polaris-pinmux-hardware-validation-2026-08-27.md).

## MKB validation branch

The source changes are pushed as [`3361c9e`](https://github.com/te9no/zmk-config-MKB2/commit/3361c9e2e40a1d05f88ba47447b4a14050699ad3) on `codex/zmk-0.4-xiao-pinmux`, based on the verified remote maintenance tip `zmk-0.4@7b02e9b`. Only `MKB.dtsi` changes: 13 added lines release unused UART/SPI in the common shield. No PR, maintenance merge, or hardware flash has been performed.

- `just.sh` pristine builds passed all 16 manifest targets: 15 keyboard variants and settings reset. Generated DTS and `.config` checks passed 258 assertions.
- [CI run 33037699063](https://github.com/te9no/zmk-config-MKB2/actions/runs/33037699063) finished successfully, including settings reset.
- All 15 keyboard variants disable the unused connector UART/SPI while preserving OLED I2C1 on P1.14/P1.15 and each module's intended controller/pins.
- XIAO battery sensing remains AIN7, power control P0.14 active-low/open-drain, and the 510 kΩ/1.51 MΩ divider. Do not copy Cornix's external A0 battery configuration into MKB.
- CDC and Bongo Cat remain configured in all 15 keyboard variants; both JOY variants retain oversampling and ADC channels 2/3.
- The maintenance baseline does not include the separately prepared 3-wire module. This pin-release change neither adds nor removes that transport and must not be described as completing the 3-wire rollout.
- Hardware validation remains pending. The build and static checks do not inherit previous hardware confirmations from another firmware revision.

## Solstice validation branch

The source changes are pushed as [`643a256`](https://github.com/te9no/zmk-config-GeaconSolstice/commit/643a2568e7bb14ed5cca7d513f4d8baa09334a62) on `codex/zmk-0.4-xiao-pinmux`, based on maintenance `zmk-0.4@6638e6c`. Four added lines across the left/right overlays disable `xiao_spi`. No PR, maintenance merge, or hardware flash has been performed.

- `just.sh` pristine builds passed all 5 targets: US/JIS left/right and settings reset. Generated DTS and `.config` checks passed 101 assertions.
- [GitHub Actions run 33037950369](https://github.com/te9no/zmk-config-GeaconSolstice/actions/runs/33037950369) finished successfully.
- All 4 keyboard targets disable connector UART/SPI and preserve matrix P1.11-P1.15/P0.09/P0.10 with interrupt P0.03.
- Left OLED I2C1 stays on P0.28/P0.29. Analog ADC channels 2/3, oversampling, and Peripheral battery display remain configured.
- Right TB keeps SPI0 on P0.04/P0.05/P0.28, CS P0.02, IRQ P0.29, CPI 800, Y inversion, and column offset 8.
- CDC and XIAO battery AIN7, power P0.14, and the 510 kΩ/1.51 MΩ divider remain configured in all 4 keyboard targets.
- Hardware validation is pending for this firmware revision; earlier successful OLED/TB/analog observations do not complete this new gate.

### Solstice recheck 2026-08-28

Read-only re-audit confirmed that the remote validation branch remains at
`643a2568e7bb14ed5cca7d513f4d8baa09334a62`, while maintenance `zmk-0.4` remains at
`6638e6c2f3331b4577b7863b99a84206722768e6`. The source change is still only four
added lines across the left/right overlays; all five targets use `xiao_ble//zmk`.

- Re-ran the generated-DTS/config checker: **101 assertions passed**, covering
  the four keyboard variants and settings-reset qualifier.
- Verified saved Solstice evidence against its SHA-256 manifest.
- Rechecked all five existing `just.sh` build logs and the successful conclusion
  of [CI run 33037950369](https://github.com/te9no/zmk-config-GeaconSolstice/actions/runs/33037950369)
  at the same source SHA. This is verification of the previous builds, not a new build.
- No source modification, firmware flash, or maintenance merge was performed.
  Hardware remains **pending** for this revision. Earlier OLED/TB/JOY confirmations
  must not be reused to close it. Next verify keys/split, left JOY/OLED and
  Peripheral battery display, right TB, and CDC on this firmware pair.

## SAA validation branch

The source changes are pushed as [`0540667`](https://github.com/te9no/zmk-config-SparAkashaAnanta/commit/0540667e1ccd3c2b83714a1bdfb0c6e0480d428f) on `codex/zmk-0.4-xiao-pinmux`, based on dedicated maintenance `zmk-0.4_validation_cormoran-zmk@4e54e1c`. Only `SAA.dtsi` changes. No firmware PR, stable/maintenance merge, or flash has been performed.

- `just.sh` pristine builds passed all 21 targets. Generated DTS and `.config` checks passed 786 assertions for unused-peripheral release and preserved configuration.
- The common shield disables default UART/SPI/I2C; selected module overlays re-enable their required controller. OLED I2C0 and LED SPI3 remain configured.
- Battery configuration now overrides `&vbatt`, retains AIN0, 470 kΩ/1.47 MΩ and NiMH thresholds, and deletes the inherited board `power-gpios` property.
- Right-side CDC and Studio remain configured. Left-side CDC remains absent as in the maintenance baseline; this change does not claim to add it.
- [CI run 33038522353](https://github.com/te9no/zmk-config-SparAkashaAnanta/actions/runs/33038522353) finished successfully.
- Both TPD+IQS variants have a separate, confirmed generated-DTS pin-ownership failure below. Passing the pin-release assertions does not establish hardware readiness for those combinations. All hardware validation remains pending.

## Separate module pin-ownership findings

These findings predate this rollout and are tracked separately as `module-pin-ownership-conflicts`. Releasing unused board defaults does not resolve a conflict between two intentionally enabled devices.

| Repository / variant | Evidence | Required follow-up |
| --- | --- | --- |
| Polaris left TPD with OLED | Generated DTS shows both devices enabled while TPD DRDY and OLED SDA use P1.14. | Confirm the physical wiring and supported module/display combination before changing the pin assignment. Then inspect generated DTS, rebuild, and verify TPD plus OLED together. No pin reassignment has been made. |
| SAA left/right `TPD_IQS` | Generated DTS at `0540667` confirms both sensors are `okay`, but the later IQS snippet selects `i2c1` P1.03/P1.14, not the TPD wiring P0.03/P0.28. The two device addresses do not resolve different physical pin assignments. This is an existing conflict, not introduced or repaired by pin release. | Confirm the actual shared-bus/wiring design and supported combination, then decide whether a controller, wiring, or target-matrix change is required. Both variants fail the separate pin-ownership gate and must not be called hardware-ready. |

The Polaris and SAA pin-release assertions are scoped to unused connector peripherals and preserved configuration; they do not claim that every independent module pin-ownership problem is resolved.

## Completion rule

A repository is complete only when every affected build target uses the intended board qualifier, unused connector nodes are disabled in generated DTS, intended module controllers are enabled on the correct pins, pristine builds pass, and representative hardware input still works. Compile success without generated-DTS inspection is insufficient.
