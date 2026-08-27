# Hardware validation record — 2026-08-22 to 2026-08-27

This is the durable Fleet record of hardware results confirmed by the owner
during the ZMK 0.4 rollout sessions. CI results are recorded separately in each
change ledger. A passed item below applies only to the named physical variant;
it must not be generalized to sibling modules.

## MKB2

- Left JOY: flashed, CDC Debug and DYA Studio connected; pointer direction,
  corrected speed, smooth 100 Hz reporting, and input continuity beyond 60
  seconds passed.
- Right TBv4: flashed; pointer direction, split relay, PMW3610 product/revision
  and CPI reporting, 22 x 22 frame capture, and streaming passed.
- Both OLEDs: Bongo Cat input/idle behavior, Central placement, Peripheral
  split-link state, and Peripheral battery display passed.
- Not yet generalized: right JOY, left TB, and right TBv3 remain hardware
  pending even though their firmware builds pass.

## GeaconSolstice

- Left and right US firmware were flashed and split input passed after the
  right-hand matrix correction.
- CDC Debug and 1200-baud boot recovery were exercised on both halves.
- DYA Studio connection/UI, right-Peripheral PMW3610 source reporting, OLED
  polarity/layout/Peripheral battery, and analog-stick runtime passed.

## GeaconPolaris

- Left LPPS and right IQS module input passed on ZMK 0.4.
- Draft PR #7 right-IQS firmware passed CDC enumeration/logging, 1200-baud
  transition from COM327 to the `I:XIAO-BOOT` drive, firmware restore, COM327
  recovery, and split/module input.
- Not yet generalized: Polaris JOY and left/right PMW3610 trackball behavior
  remain hardware pending; right TB/TPD PR #7 variants also remain pending.

## Cornix / Madula

- Madula firmware flash, two-CDC enumeration, and DYA Studio connection passed.
- Madula Trackball passed PMW3610 initialization (`0x3e`/revision `0x01`,
  `ready=true`, `init_err=0`), source readiness, and owner-confirmed pointer
  input after the XIAO pinmux fix. Cornix `main@794987c`, the `just.sh` 12/12
  manifest, and Actions run 32991787396 are the integration evidence.
- The Trackball item is complete. The 1200-baud transition and physical IQS
  input remain separate pending checks and must not be shown as Trackball work.

## Evidence policy

These are owner-observed hardware results, not automated CI assertions. Future
results should name the exact variant, date, transport/drive where relevant,
and the observable pass condition before a sibling variant is marked passed.
