# PR and ledger audit — 2026-08-24

The authoritative inventory is `users/te9no/fleet.toml`. All te9no-owned
repositories were checked for open pull requests and compared with their ledger
tracking. No external repository was changed.

## Decisions

- Merged: GeaconSolstice [PR #5](https://github.com/te9no/zmk-config-GeaconSolstice/pull/5) into `zmk-0.4` at `6638e6c`. Its only diff directly pins ZMK to `cormoran/zmk@e5c9b69`; CI, both US halves, right input, OLED, DYA Studio UI, and analog-stick hardware validation passed. Stable `main` was not changed.
- Retained: Cornix [PR #3](https://github.com/te9no/zmk-keyboard-cornix/pull/3) is Draft against `zmk-0.4`. CI and CDC/DYA Studio verification passed, but a physical Madula trackball is not attached.
- Closed: none. No open te9no PR was an evidenced duplicate or superseded change.

## Next actions

1. **Cornix — PR #3 (highest priority):** attach the physical Madula trackball module; flash the validated Trackball firmware; verify PMW3610 input direction, local-source diagnostics, and a frame capture in DYA Studio. Completion requires all three hardware observations, then the Draft can be reconsidered for `zmk-0.4` only. It remains Draft because the sensor is not attached.
2. **SAA — no open PR:** use the existing validation branch with the physical JOY/IQS modules to confirm runtime input, split behavior, and CDC parity. Completion is a hardware ledger update only; do not promote `master`.
3. **Remaining backlog (MDK, MRM, Torabo, Berkut51, koZakura, Sparagmos):** first classify driver compatibility and obtain the required physical module before any validation-branch work. No stable `main` or `master` promotion is a candidate.
