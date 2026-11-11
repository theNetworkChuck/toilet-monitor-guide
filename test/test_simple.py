# Runs pi/toilet_simple.py against a fake clock + fake switch: python3 test/test_simple.py pi/toilet_simple.py
import sys, types, io, contextlib
clock = [0.0]
# (start, end, float_up): full, 0.4 s slosh, full, real 5 s flush, full, 0.9 s slosh, full, 3 s flush, full
timeline = [(0, 5, True), (5, 5.4, False), (5.4, 10, True), (10, 15, False), (15, 20, True),
            (20, 20.9, False), (20.9, 25, True), (25, 28, False), (28, 40, True)]
def up(t): return next(u for a, b, u in timeline if a <= t < b)
class Button:
    def __init__(self, pin, pull_up): assert pin == 17 and pull_up
    @property
    def is_pressed(self): return not up(clock[0])  # wires connect when the float drops
class Stop(Exception): pass
def sleep(s):
    clock[0] += s
    if clock[0] >= 39: raise Stop
sys.modules['gpiozero'] = types.SimpleNamespace(Button=Button)
import time; time.sleep = sleep
out = io.StringIO()
try:
    with contextlib.redirect_stdout(out):
        exec(open(sys.argv[1]).read(), {'__name__': '__main__'})
except Stop: pass
print(out.getvalue().strip())
assert out.getvalue().split() == ['FLUSH!', '1', 'FLUSH!', '2'], 'expected exactly 2 flushes'
print('PASS: 2 real flushes counted, 2 sloshes ignored')
