from pump_controller import PumpController

ctrl = PumpController(log_file='experiment.log')
ctrl.add_harvard('pump_a', port='COM6')
ctrl.add_new_era('pump_b', port='COM7', address=0)
ctrl.add_new_era('pump_c', port='COM7', address=1)

try:
    # Flush all three pumps simultaneously at 10760 µL/min for 10 minutes (107600 µL each)
    # NOTE: volume must still be passed in mL — 107600 µL = 107.6 mL
    ctrl.run_parallel([
    {'pump_id': 'pump_a', 'rate': 10.76, 'units': 'ml/min', 'volume': 107.6, 'diameter_mm': 12.36, 'direction': 'infuse'},
    {'pump_id': 'pump_b', 'rate': 10.76, 'units': 'ml/min', 'volume': 107.6, 'diameter_mm': 12.36, 'direction': 'infuse'},
    {'pump_id': 'pump_c', 'rate': 10.76, 'units': 'ml/min', 'volume': 107.6, 'diameter_mm': 12.36, 'direction': 'infuse'},
])

except Exception as e:
    print(f'Experiment error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()