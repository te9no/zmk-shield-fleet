# Solstice right CDC recheck — 2026-08-30

The owner requested rechecking the right CDC after accepting the OLED fix and
other operation. Tested the installed US validation firmware at
`643a2568e7bb14ed5cca7d513f4d8baa09334a62`; no code changes or settings reset.

- Right COM50 opened at 115200 baud and supplied diagnostic text.
- Changed the open port to 1200 baud with DTR asserted for two seconds, then
  released DTR/RTS and closed. The driver logged the baud-rate change.
- After about **797 ms**, H: UF2 bootloader appeared; COM50 disappeared and
  bootloader COM235 appeared. USB and bootloader identity matched Solstice right.
- Application readback matched the CI `33037950369` right US artifact at
  **1133/1133 blocks**, SHA-256
  `ca38bb9d80aebb3d8fc17f0e7177b1fb8439a5cb1ded5844f3ce804379eef4f2`.
- Restored that exact UF2. COM50 reopened at 115200 baud and the bootloader
  volume disappeared. Twelve seconds of logging captured 5405 characters,
  including the following relevant messages:

```text
[00:00:00.299,011] <inf> zmk_cdc_acm_bootloader_trigger: CDC ACM bootloader trigger initialized with line-control polling
*** Booting Zephyr OS build 10ba6d0cb38b ***
[00:00:00.566,558] <inf> pmw3610: PMW3610 initialized
[00:00:03.161,651] <inf> zmk: Peripheral connected, blinking blue
```

**Passed:** right CDC log reception, 1200-baud boot, application identity,
normal CDC recovery, PMW3610 initialization, and split connection.
The earlier unresponsive right CDC observations concerned the previously
installed image and remain historical; this test establishes the current
candidate's result. It does not diagnose the earlier failure's cause.

The device was left running the same US image. Serial handles were closed.
Left firmware and stored settings were untouched. The full readback was read
only into memory and was not saved or published; only application block-match
counts and hashes were retained. Private summaries and filtered diagnostic
logs are in `.zmk-workspace/evidence/solstice-right-cdc-recheck-20260830/`.
