# Polaris pin-release hardware validation

Date: 2026-08-27

The owner identified the connected modules as **left JOY / right TB** before flashing the UF2 files built from source [`8421728`](https://github.com/te9no/zmk-config-GeaconPolaris/commit/84217286bbc5d064b1d6a3e3b3f671017e687942) on `codex/zmk-0.4-xiao-pinmux`. This report separates firmware transfer, boot/CDC/split connectivity, and actual module operation. A successful build or flash is not a successful sensor test.

## Flash and boot results

| Side | Trigger and bootloader | Result | Not yet verified |
| --- | --- | --- | --- |
| Left JOY | Studio COM326 at 1200 baud → H drive → Debug COM325 | UF2 written; debug port returned; Zephyr boot banner observed. | JOY movement, direction/speed/continuity and OLED visual appearance. |
| Right TB | COM327 at 1200 baud → I drive → COM327 | UF2 written; CDC and Zephyr boot returned; BLE split connection established. | Pointer/module input. PMW3610 initialization failed as detailed below. |

The earlier left-side trigger attempt on Debug COM325 did not enter the bootloader. COM326, the Studio endpoint, is the working trigger port for this firmware. This port-selection result is not classified as a CDC hardware failure. Split connection success does not prove sensor reports were relayed.

Local CDC evidence is retained under the log basenames `hardware-left-joy-flash.log` and `hardware-right-tb-flash.log`. The public ledger records the relevant observations without publishing local absolute paths or unrelated device identifiers.

## Right TB sensor failure

On the new `8421728` firmware:

- The 3-wire controller initialized and startup transfers reported result `0`.
- OBSERVATION read `0xff` and Product ID read `0x00`, not the expected `0x3e`.
- PMW3610 initialization failed at step 2 after the initial attempt plus 10 retries, 11 attempts in total.
- CDC, boot and the BLE split connection still worked. These successes do not clear the sensor-initialization failure.

The cause is not established. Transfer result `0` only reports that the controller completed the transaction; it does not establish that the sensor returned valid data.

## Comparison rollback

Only the right half was reflashed with the previous `zmk-0.4` distribution UF2. Its size is **616,960 bytes**, and its SHA-256 is:

```text
2dbb49c0036be7dbf3d2fa94b2137acac471bc646ce35ba779eab31f81186f78
```

The diagnostic comparison confirmed that this hash matches the distribution UF2 at maintenance revision `ed5cba4`; it is not merely a similarly named local file.

The baseline flash used COM327 → I and successfully returned to CDC/Zephyr boot and split connectivity. However, **the same OBSERVATION `0xff`, Product ID `0x00`, and step-2 failure after 11 attempts occurred**. Evidence is retained as `hardware-right-tb-baseline.log`.

The rollback/comparison procedure is complete, but it did **not** recover PMW3610 operation. Reproduction on both the old and new UF2 means a regression caused by the XIAO pin-release change has not been demonstrated. This comparison also does not prove a specific electrical or firmware root cause.

The diagnostic source comparison found matching SHA-256 values for the old/new 3-wire C implementation; the `TB_R` overlay/config differ only in line endings. As a hypothesis, OBSERVATION command `0x2d` ending in bit 1 followed by `0xff`, and Product-ID command `0x00` ending in bit 0 followed by `0x00`, are consistent with an undriven SDIO line retaining the final command level. This is **not a confirmed diagnosis** of wiring, power, or sensor failure.

## Current state and next checks

- Left remains on the new `8421728` JOY firmware; JOY input and OLED visual checks are pending.
- Right remains on the old, hash-verified `ed5cba4` distribution UF2; PMW initialization still fails.
- The user has been asked to disconnect right USB, turn off its battery, check the TB module connection, and reconnect. These complete-power-cycle/physical checks are pending. Do not mark the sensor or overall hardware gate passed until it actually initializes and produces valid input.
- No firmware source change, maintenance/stable merge, or firmware PR was made for this comparison.
- The successful right-TB pointer/split observations recorded on 2026-08-26 remain historical evidence. This report adds a new failed observation and baseline comparison; it does not erase or transfer the earlier result to the current session.
