# Madula IQS9151 validation — 2026-08-28

## Integrated source

Owner authorized integration after confirming pointer direction. Cornix firmware
[main@578c9f1](https://github.com/te9no/zmk-keyboard-cornix/commit/578c9f1f94c1a3d2bdd0b7c33ba2fe02c58dac72)
contains SDA P1.14 (J4.3/MOTION), `CONFIG_INPUT_IQS9151_ROTATE_270=y`
(clockwise 90 degrees), and the corrected README pin table.
SCL P1.13, IRQ P1.12, TWIM at 400 kHz and the pinned ShiniNet driver
`08a6fd19c5aa5ae7f11daf371b5a391cd8596783` are unchanged. No upstream PR was made.

## Diagnosis and hardware evidence

| Diagnostic | Observed result |
| --- | --- |
| Original SDA P1.15, TWIM | No product-ID or initialization-complete milestone |
| Original SDA P1.15, TWI | Same failure; backend-only change did not resolve it |
| SDA P1.14, TWIM, rotation 0 | Product ID `0x09bc`, initialization complete; owner reported right moved up |
| SDA P1.14, TWIM, rotation 270 | Product ID `0x09bc`, initialization complete; owner confirmed direction OK |

The final diagnostic was built with `just.sh`, flashed through the identity-checked
CDC 1200-baud bootloader path, and returned to runtime CDC logging. Its SHA256 is
`62711f26fb23e5d5a53a914fe56493bff8dcc6413a019d077d7fedda00e38191`.
The captured boot reports product ID at 0.830474 s, initialization complete at
2.860290 s, and USB endpoint selection at 3.107513 s. Three early RDY timeout
warnings and a mid-init capture gap remain; this is not a warning-free boot claim.
Raw logs and stable USB identifiers are deliberately not published.

## Production build and limits

The integrated source passed `just.sh --profile madula-lpps-validation build madula_iqs`
without diagnostic overlays. Generated DTS exactly matches the verified rotation
diagnostic; rotation 270 and TWIM are enabled. Standard CDC Debug/boot support is
retained, without promoting temporary verbose diagnostic logging.
Production UF2 SHA256: `6191ba66643c7272768436b94a8df48dee56494a0342a0157823ebb2e9c3d926`.
FLASH: 322564 B; RAM: 90796 B.
The full-matrix [firmware CI run](https://github.com/te9no/zmk-keyboard-cornix/actions/runs/33127943387)
is queued; the successful local target build is recorded separately from CI.

The owner's hardware confirmation applies to the diagnostic above, not a new
flash of the production artifact. Pointer input, direction, sensor initialization,
and the IQS variant's CDC flash/recovery path passed. Gestures, cold power-up,
long-duration operation, and split connectivity were not independently verified.
The separate main/Trackball 1200-baud gate remains pending; IQS results do not
automatically validate Trackball or any other variant.
