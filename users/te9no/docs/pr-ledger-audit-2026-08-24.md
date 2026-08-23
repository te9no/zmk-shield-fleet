# PR and ledger audit — 2026-08-24

The authoritative inventory is `users/te9no/fleet.toml`. All te9no-owned
repositories were checked for open pull requests and compared with their ledger
tracking. No external repository was changed.

## Decisions

- Merged: GeaconSolstice [PR #5](https://github.com/te9no/zmk-config-GeaconSolstice/pull/5) into `zmk-0.4` at `6638e6c`. Its only diff directly pins ZMK to `cormoran/zmk@e5c9b69`; CI, both US halves, right input, OLED, DYA Studio UI, and analog-stick hardware validation passed. Stable `main` was not changed.
- Retained: Cornix [PR #3](https://github.com/te9no/zmk-keyboard-cornix/pull/3) is Draft against `zmk-0.4`. CI and CDC/DYA Studio verification passed, but a physical Madula trackball is not attached.
- Retained: [dongle-display PR #3](https://github.com/te9no/zmk-dongle-display/pull/3) is the Draft LVGL 9/ZMK 0.4 migration against that module's `main`. Its module workflow is currently failing at `west update`, and Solstice ultimately selected the upstream module revision for its validated OLED layout; keep it Draft rather than merging to module `main`.
- Closed: [dongle-display PR #4](https://github.com/te9no/zmk-dongle-display/pull/4) as superseded. It was two commits stacked on #3, but its explicit-color/mono-theme experiment is recorded as failed on Solstice hardware. It must not be folded into #3 or merged to `main`; the working Solstice configuration uses the upstream ZMK 0.4 revision instead.
- Retained: [MLX90393 PR #1](https://github.com/te9no/zmk-driver-MLX90393/pull/1) is a clean Draft with the singular ZMK 0.4 endpoint API change. MKB2 build evidence exists, but MLX90393 hardware validation is still absent, so it remains Draft and is not eligible for module-`main` merge.

## Next actions

1. **Cornix — PR #3 (highest priority):** attach the physical Madula trackball module; flash the validated Trackball firmware; verify PMW3610 input direction, local-source diagnostics, and a frame capture in DYA Studio. Completion requires all three hardware observations, then the Draft can be reconsidered for `zmk-0.4` only. It remains Draft because the sensor is not attached.
2. **Runnable now — dongle-display PR #3:** diagnose and correct its `west update` workflow failure, then build the module against a disposable Solstice-style ZMK 0.4 configuration. Completion is a green module CI run; it remains Draft until a display-specific hardware test, and it is not a `main` merge candidate.
3. **Hardware waiting — MLX90393 PR #1:** attach the MKB2 MLX90393 module and verify motion, button/Shift behavior, and ZMK endpoint-report delivery. Completion requires those runtime observations plus a green module CI run; it remains Draft until then.
4. **SAA — no open PR:** use the existing validation branch with the physical JOY/IQS modules to confirm runtime input, split behavior, and CDC parity. Completion is a hardware ledger update only; do not promote `master`.
5. **Remaining backlog (MDK, MRM, Torabo, Berkut51, koZakura, Sparagmos):** first classify driver compatibility and obtain the required physical module before any validation-branch work. No stable `main` or `master` promotion is a candidate.
