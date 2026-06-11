import sys
sys.path.insert(0, 'src')

import signal
from pump_controller import PumpController

DIAMETER = 12.36   # mm
RATE     = 38      # µL/min
INCREMENT = 0.001  # mL (= 1 µL, controller takes mL)
MAX_VOL   = 19     # µL, hard limit per side

ctrl = None

def signal_handler(signum, frame):
    print('\n[KEYBOARD INTERRUPT] Stopping all pumps...')
    if ctrl:
        ctrl.stop_all()
        ctrl.close_all()
    print('[CLOSED] All connections closed.')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

ctrl = PumpController(log_file='experiment.log')

ctrl.add_new_era('pump_b', port='COM7', address=0)
ctrl.add_new_era('pump_c', port='COM7', address=1)

balance = 0  # µL, positive = pump_b side infused more, negative = pump_c side

print('Pump CLI ready. Rate: 38 µL/min | Increment: 1 µL | Max: ±19 µL')
print('  1 = pump_b infuse / pump_c withdraw')
print('  2 = pump_c infuse / pump_b withdraw')
print('  Ctrl+C to quit\n')

try:
    while True:
        print(f'Balance: {balance:+d} µL  (pump_b net: {balance:+d}, pump_c net: {-balance:+d})')
        choice = input('Enter 1 or 2: ').strip()

        if choice == '1':
            if balance >= MAX_VOL:
                print(f'  At max +{MAX_VOL} µL. Press 2 to reverse.\n')
                continue
            ctrl.run_parallel([
                {'pump_id': 'pump_b', 'rate': RATE, 'units': 'ul/min', 'volume': INCREMENT, 'diameter_mm': DIAMETER, 'direction': 'infuse'},
                {'pump_id': 'pump_c', 'rate': RATE, 'units': 'ul/min', 'volume': INCREMENT, 'diameter_mm': DIAMETER, 'direction': 'withdraw'},
            ])
            balance += 1

        elif choice == '2':
            if balance <= -MAX_VOL:
                print(f'  At max -{MAX_VOL} µL. Press 1 to reverse.\n')
                continue
            ctrl.run_parallel([
                {'pump_id': 'pump_c', 'rate': RATE, 'units': 'ul/min', 'volume': INCREMENT, 'diameter_mm': DIAMETER, 'direction': 'infuse'},
                {'pump_id': 'pump_b', 'rate': RATE, 'units': 'ul/min', 'volume': INCREMENT, 'diameter_mm': DIAMETER, 'direction': 'withdraw'},
            ])
            balance -= 1

        else:
            print('  Invalid. Enter 1 or 2.\n')
            continue

        print(f'  Done. New balance: {balance:+d} µL\n')

except Exception as e:
    print(f'Experiment error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()