# Solstice XIAO pin-release integration — 2026-08-30

The owner requested progressing the Solstice XIAO qualifier / unused-peripheral
item to completion. The hardware-verified candidate was promoted to `zmk-0.4`;
stable firmware `main` was not changed. This update is Solstice-only.

## Integrated source

- [PR #6](https://github.com/te9no/zmk-config-GeaconSolstice/pull/6) merged into
  `zmk-0.4` at `7f64859869022d5d7b65afdd4aee0a0d1b45a9a2`.
- Its Git tree exactly equals tested source
  `25dbb3f3061f3b5f1c8729025fd15e3b281dd34b`.
- Changes relative to the old maintenance branch are limited to both halves'
  unused `xiao_spi` disable and the left OLED lock-text disable. Existing XIAO
  ZMK qualifier, battery configuration and module pin assignments are retained.
  The right trackball continues using `spi0`.
- Stable `main` remains `9dbc6fb02f124e9f39841f3bab93bb68da44ac74`.
- The unrelated local `Solstice_JIS.svg` edit was not committed or included.

## Build and generated configuration

- Pin-release base `643a256`: existing root `just.sh` 5/5 targets, CI
  [33037950369](https://github.com/te9no/zmk-config-GeaconSolstice/actions/runs/33037950369),
  and generated DTS/config audit (101 assertions) passed.
- The OLED addition was built using the unchanged root `just.sh`, pristine
  left US/JIS 2/2. Generated DTS files are byte-identical to the pin-release
  baseline; the lock-text widget is excluded and other widgets are preserved.
- Before committing, the config SHA-256 and both left artifact hashes were
  rechecked against the [OLED evidence](solstice-oled-lock-text-2026-08-30.md).
  The tested uncommitted config is now recorded in commit `25dbb3f`; no further
  source edit was made for promotion.
- Final source [CI 33306076773](https://github.com/te9no/zmk-config-GeaconSolstice/actions/runs/33306076773)
  passed all five targets: left/right US, left/right JIS, and settings_reset.
  The reset image was only built, never flashed.
- Post-merge [CI 33306224704](https://github.com/te9no/zmk-config-GeaconSolstice/actions/runs/33306224704)
  also passed all five targets at `7f64859`. This is recorded separately from
  the source CI and the prior hardware evidence.

## Hardware evidence and limits

- The owner accepted the actual US pair with **「OK消えました 他も動作問題ないです」**.
- Tested left US SHA-256:
  `b1c151397da708832a3c1e83f72db52850d0d684174fa2b04455ccb7ef8929f6`.
- Tested right US SHA-256:
  `ca38bb9d80aebb3d8fc17f0e7177b1fb8439a5cb1ded5844f3ce804379eef4f2`.
- [Right CDC recheck](solstice-right-cdc-recheck-2026-08-30.md) passed log
  reception, 1200-baud boot, 1133/1133 application-block readback, normal CDC
  return, PMW3610 initialization and split connection.
- No new flashing, hardware measurement or settings reset was performed during
  integration. The evidence refers to the previously tested artifacts; it is
  not a claim that a newly generated post-merge artifact was flashed.
- JIS hardware, extended-duration behavior, and resolution of left saved-keymap
  load errors are not inferred from the acceptance or the CI results.

The completed hardware action `solstice-pinmux-hardware` is removed from the
next-action list. The ledger keeps source/build, hardware and integration
evidence distinct. Previous right CDC failures remain historical observations,
not unresolved failures of the accepted candidate.
