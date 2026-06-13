import sys
sys.path.insert(0, 'src')

import signal
from pump_controller import PumpController





# ---------------------CONFIG ZONE START------------------------------

DIAMETER = 12.36   # mm
RATE     = 38      # µL/min
VOLUME   = 1   # mL (= 19 µL)

# ---------------------CONFIG ZONE END------------------------------




















ctrl = None

def signal_handler(signum, frame):
    print('\n[KEYBOARD INTERRUPT] Stopping all pumps...')
    if ctrl:
        ctrl.stop_all()
        ctrl.close_all()
    print('[CLOSED] All connections closed.')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

ctrl = PumpController(log_file='logs/experiment.log')

#ctrl.add_new_era('pump_b', port='COM7', address=0)
#ctrl.add_new_era('pump_c', port='COM7', address=1)

ctrl.add_new_era('pump_b', port='COM7', address=0)
ctrl.add_new_era('pump_c', port='COM7', address=0)

print('Pump CLI ready. Rate: 38 µL/min | Volume: 19 µL')
print('  1 = pump_b infuse / pump_c withdraw')
print('  2 = pump_c infuse / pump_b withdraw')
print('  Ctrl+C to quit\n')

try:
    while True:
        choice = input('Enter 1 or 2: ').strip()

        if choice == '1':
            ctrl.run_parallel([
                {'pump_id': 'pump_b', 'rate': RATE, 'units': 'ul/min', 'volume': VOLUME, 'diameter_mm': DIAMETER, 'direction': 'infuse'},
                {'pump_id': 'pump_c', 'rate': RATE, 'units': 'ul/min', 'volume': VOLUME, 'diameter_mm': DIAMETER, 'direction': 'withdraw'},
            ])
            print('  Done.\n')

        elif choice == '2':
            ctrl.run_parallel([
                {'pump_id': 'pump_c', 'rate': RATE, 'units': 'ul/min', 'volume': VOLUME, 'diameter_mm': DIAMETER, 'direction': 'infuse'},
                {'pump_id': 'pump_b', 'rate': RATE, 'units': 'ul/min', 'volume': VOLUME, 'diameter_mm': DIAMETER, 'direction': 'withdraw'},
            ])
            print('  Done.\n')

        else:
            print('  Invalid. Enter 1 or 2.\n')

except Exception as e:
    print(f'Experiment error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()