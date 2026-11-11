# 3. Wire the float switch

[◀ Flash the Pi](02-flash-the-pi.md) · Next: [Test it on the desk ▶](04-test-on-the-desk.md)

**Do this with the Pi unplugged.** You don't want to short anything.

The float switch has two wires. It doesn't matter which wire goes where.

| Float switch wire | Pi physical pin | What it is |
|---|---|---|
| Either wire | **Pin 9** | Ground (GND) |
| The other wire | **Pin 11** | GPIO17 |

```
          Pi 40-pin header (USB ports pointing down, SD card at the top)

               3.3V  (1) (2)  5V
              GPIO2  (3) (4)  5V
              GPIO3  (5) (6)  GND
              GPIO4  (7) (8)  GPIO14
   ──► GND ──────── (9) (10)  GPIO15
   ──► GPIO17 ───── (11) (12)  GPIO18
                     ...
```

Pin 1 is the corner pin closest to the SD card slot, on the inside row. Pins 9 and 11 are both on that inside row, two and three spots down from pin 5.

I slid two jumper wires onto pins 9 and 11 and wrapped the bare float switch wires around the other ends. Very jank. All you need is metal touching metal. Solder them or use a connector when you're happy with it (I said I would. I won't.)

## Why only two wires?

You'd expect to need a resistor here. You don't. The Pi has one built in, called a **pull-up resistor**, and our code turns it on:

- The pull-up weakly ties pin 11 to 3.3 volts. Nothing pulling on it, so it reads **1** (high).
- When the float drops and the switch closes, pin 11 is connected straight to ground. Now it reads **0** (low).

Without the pull-up, the pin would just float, picking up stray electrical noise and reading random 1s and 0s. You'd be seeing flushes all the time.

> Pin 11 is called **GPIO17** in code. Physical pin numbers count positions on the header; GPIO numbers are what the chip calls them. It's a weird Pi thing. The code uses `17`.

Now plug the Pi in and SSH to it.
