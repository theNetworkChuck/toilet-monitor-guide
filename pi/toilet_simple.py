from gpiozero import Button
import time

switch = Button(17, pull_up=True)   # float switch on GPIO17 + ground
flushes = 0

while True:
    if switch.is_pressed:            # wires connected = float dropped
        time.sleep(1)                # wait one second...
        if switch.is_pressed:        # ...still low? that's a real flush
            flushes += 1
            print("FLUSH!", flushes)
            while switch.is_pressed:       # wait for the tank to refill
                time.sleep(0.1)
    time.sleep(0.1)
