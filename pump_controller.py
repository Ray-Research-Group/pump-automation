"""
Unified Pump Controller
Wraps Harvard Apparatus Pump 11 Elite and New Era NE-4002X behind
a single interface. Experiment procedures use this — never the drivers directly.

Usage:
    from pump_controller import PumpController

    ctrl = PumpController()
    ctrl.add_harvard('harvard_0', port='COM6')
    ctrl.add_new_era('new_era_0', port='COM7', address=0)
    ctrl.add_new_era('new_era_1', port='COM7', address=1)  # same port, diff address

    ctrl.infuse('harvard_0', rate=1.0, units='ml/min', volume=5.0, diameter_mm=14.43)
    ctrl.run_all()
    ctrl.wait_until_all_done()
    ctrl.close_all()
"""

import time
import threading
from datetime import datetime
from harvard_elite import HarvardElite
from new_era import NewEraNetwork, NewEraPump


# ── ABSTRACT BASE ─────────────────────────────────────────────────────────────

class PumpInterface:
    """
    Abstract interface all pump wrappers must implement.
    Never instantiate directly.
    """

    def set_diameter(self, mm): raise NotImplementedError
    def set_rate(self, rate, units): raise NotImplementedError
    def set_volume(self, volume, units='ml'): raise NotImplementedError
    def set_direction(self, direction): raise NotImplementedError
    def run(self): raise NotImplementedError
    def stop(self): raise NotImplementedError
    def is_running(self): raise NotImplementedError
    def wait_until_done(self, poll_interval=0.5, timeout=300): raise NotImplementedError
    def get_volume_dispensed(self): raise NotImplementedError
    def get_status(self): raise NotImplementedError
    def infuse(self, rate, units, volume, diameter_mm): raise NotImplementedError
    def withdraw(self, rate, units, volume, diameter_mm): raise NotImplementedError


# ── HARVARD WRAPPER ───────────────────────────────────────────────────────────

class HarvardWrapper(PumpInterface):
    """
    Wraps HarvardElite to match the unified PumpInterface.
    Normalizes unit strings to Harvard format.
    """

    # Validate and pass through — Harvard driver accepts full unit strings
    RATE_UNITS = {
        'ul/min': 'ul/min',
        'ml/min': 'ml/min',
        'ul/hr':  'ul/hr',
        'ml/hr':  'ml/hr',
        'nl/min': 'nl/min',
        'pl/min': 'pl/min',
    }

    def __init__(self, port, baudrate=9600, timeout=2):
        self._pump = HarvardElite(port, baudrate, timeout)
        self._direction = 'infuse'

    def _normalize_units(self, units):
        u = units.lower().replace(' ', '')
        result = self.RATE_UNITS.get(u)
        if result is None:
            raise ValueError(f'Invalid units: {units}. Valid: {list(self.RATE_UNITS.keys())}')
        return result

    def set_diameter(self, mm):
        return self._pump.set_diameter(mm)

    def set_rate(self, rate, units='ml/min'):
        return self._pump.set_rate(rate, self._normalize_units(units))

    def set_withdraw_rate(self, rate, units='ml/min'):
        return self._pump.set_withdraw_rate(rate, self._normalize_units(units))

    def set_volume(self, volume, units='ml'):
        return self._pump.set_volume(volume, units)

    def set_direction(self, direction):
        self._direction = direction.lower()  # stores 'infuse' or 'withdraw'

    def run(self):
        if self._direction == 'infuse':
            return self._pump.infuse()
        elif self._direction == 'withdraw':
            return self._pump.withdraw()
        else:
            raise ValueError(f"Invalid direction: {self._direction}")

    def stop(self):
        return self._pump.stop()

    def is_running(self):
        return self._pump.is_running()

    def wait_until_done(self, poll_interval=0.5, timeout=300):
        return self._pump.wait_until_done(poll_interval, timeout)

    def get_volume_dispensed(self):
        return self._pump.get_volume_dispensed()

    def get_status(self):
        return self._pump.get_status()

    def infuse(self, rate, units, volume, diameter_mm):
        self.set_diameter(diameter_mm)
        self.set_rate(rate, units)
        self.set_volume(volume)
        self.set_direction('infuse')
        self.run()
        self.wait_until_done()

    def withdraw(self, rate, units, volume, diameter_mm):
        self.set_diameter(diameter_mm)
        self.set_withdraw_rate(rate, units)
        self.set_volume(volume)
        self.set_direction('withdraw')
        self.run()
        self.wait_until_done()

    def close(self):
        self._pump.close()


# ── NEW ERA WRAPPER ───────────────────────────────────────────────────────────

class NewEraWrapper(PumpInterface):
    """
    Wraps NewEraPump to match the unified PumpInterface.
    """

    def __init__(self, pump: NewEraPump):
        self._pump = pump

    def set_diameter(self, mm):
        return self._pump.set_diameter(mm)

    def set_rate(self, rate, units='ml/hr'):
        return self._pump.set_rate(rate, units)

    def set_volume(self, volume, units='ml'):
        return self._pump.set_volume(volume * 1000)  # mL -> µL, drop units arg

    def set_direction(self, direction):
        return self._pump.set_direction(direction)

    def run(self):
        return self._pump.run()

    def stop(self):
        return self._pump.stop()

    def is_running(self):
        return self._pump.is_running()

    def wait_until_done(self, poll_interval=0.5, timeout=300):
        return self._pump.wait_until_done(poll_interval, timeout)

    def get_volume_dispensed(self):
        return self._pump.get_volume_dispensed()

    def get_status(self):
        return self._pump.get_status()

    def infuse(self, rate, units, volume, diameter_mm):
        return self._pump.infuse(rate, units, volume, diameter_mm)

    def withdraw(self, rate, units, volume, diameter_mm):
        return self._pump.withdraw(rate, units, volume, diameter_mm)

    def close(self):
        pass  # network owns the serial port, not individual pumps


# ── LOGGER ───────────────────────────────────────────────────────────────────

class PumpLogger:
    def __init__(self, log_file=None):
        self.log_file = log_file

    def log(self, pump_id, action, detail=''):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        msg = f'[{ts}] [{pump_id}] {action}'
        if detail:
            msg += f' — {detail}'
        print(msg)
        if self.log_file:
            with open(self.log_file, 'a') as f:
                f.write(msg + '\n')


# ── UNIFIED CONTROLLER ────────────────────────────────────────────────────────

class PumpController:
    """
    Central controller for all pumps in the experiment.
    Owns pump registration, coordinated operations, and logging.

    Example:
        ctrl = PumpController(log_file='experiment.log')
        ctrl.add_harvard('pump_a', port='COM6')
        ctrl.add_new_era('pump_b', port='COM7', address=0)

        ctrl.infuse('pump_a', rate=1.0, units='ml/min', volume=5.0, diameter_mm=14.43)
        ctrl.run_all()
        ctrl.wait_until_all_done()
    """

    def __init__(self, log_file=None):
        self._pumps = {}             # id -> PumpInterface
        self._networks = {}          # port -> NewEraNetwork
        self._logger = PumpLogger(log_file)

    # ── REGISTRATION ─────────────────────────────────────

    def add_harvard(self, pump_id, port, baudrate=9600):
        """Register a Harvard Apparatus Pump 11 Elite."""
        wrapper = HarvardWrapper(port, baudrate)
        self._pumps[pump_id] = wrapper
        self._logger.log(pump_id, 'REGISTERED', f'Harvard Elite on {port}')
        return wrapper

    def add_new_era(self, pump_id, port, address=0, baudrate=19200):
        """
        Register a New Era pump. Multiple pumps can share a port (daisy chain).
        """
        if port not in self._networks:
            self._networks[port] = NewEraNetwork(port, baudrate)
        network = self._networks[port]
        pump = network.add_pump(address)
        wrapper = NewEraWrapper(pump)
        self._pumps[pump_id] = wrapper
        self._logger.log(pump_id, 'REGISTERED', f'New Era on {port} address {address}')
        return wrapper

    def get(self, pump_id) -> PumpInterface:
        """Get a pump wrapper by ID."""
        if pump_id not in self._pumps:
            raise KeyError(f'No pump registered with id: {pump_id}')
        return self._pumps[pump_id]

    # ── SINGLE PUMP OPERATIONS ────────────────────────────

    def infuse(self, pump_id, rate, units, volume, diameter_mm):
        """Set params and infuse. Blocks until done."""
        self._logger.log(pump_id, 'INFUSE', f'{rate} {units}, {volume} ml, dia {diameter_mm} mm')
        self.get(pump_id).infuse(rate, units, volume, diameter_mm)
        self._logger.log(pump_id, 'INFUSE DONE')

    def withdraw(self, pump_id, rate, units, volume, diameter_mm):
        """Set params and withdraw. Blocks until done."""
        self._logger.log(pump_id, 'WITHDRAW', f'{rate} {units}, {volume} ml, dia {diameter_mm} mm')
        self.get(pump_id).withdraw(rate, units, volume, diameter_mm)
        self._logger.log(pump_id, 'WITHDRAW DONE')

    def stop(self, pump_id):
        self._logger.log(pump_id, 'STOP')
        self.get(pump_id).stop()

    def run(self, pump_id):
        self._logger.log(pump_id, 'RUN')
        self.get(pump_id).run()

    def wait_until_done(self, pump_id, poll_interval=0.5, timeout=300):
        self.get(pump_id).wait_until_done(poll_interval, timeout)
        self._logger.log(pump_id, 'DONE')

    def is_running(self, pump_id):
        return self.get(pump_id).is_running()

    def get_status(self, pump_id):
        return self.get(pump_id).get_status()

    def get_volume_dispensed(self, pump_id):
        return self.get(pump_id).get_volume_dispensed()

    # ── MULTI PUMP OPERATIONS ─────────────────────────────

    def stop_all(self):
        """Stop all registered pumps immediately."""
        self._logger.log('ALL', 'STOP ALL')
        for pump_id, pump in self._pumps.items():
            try:
                pump.stop()
            except Exception as e:
                self._logger.log(pump_id, 'STOP ERROR', str(e))

    def run_all(self):
        """Start all registered pumps."""
        self._logger.log('ALL', 'RUN ALL')
        for pump_id, pump in self._pumps.items():
            try:
                pump.run()
                self._logger.log(pump_id, 'RUNNING')
            except Exception as e:
                self._logger.log(pump_id, 'RUN ERROR', str(e))

    def wait_until_all_done(self, poll_interval=0.5, timeout=300):
        """Block until all pumps have stopped."""
        self._logger.log('ALL', 'WAITING FOR ALL TO FINISH')
        start = time.time()
        while any(p.is_running() for p in self._pumps.values()):
            if time.time() - start > timeout:
                self.stop_all()
                raise TimeoutError('Not all pumps finished within timeout — all stopped')
            time.sleep(poll_interval)
        self._logger.log('ALL', 'ALL DONE')

    def run_parallel(self, configs):
        threads = []
        errors = {}

        def _run(cfg):
            pid = cfg['pump_id']
            try:
                pump = self.get(pid)
                direction = cfg.get('direction', 'infuse')
                if direction == 'withdraw':
                    pump.withdraw(cfg['rate'], cfg['units'], cfg['volume'], cfg['diameter_mm'])
                else:
                    pump.infuse(cfg['rate'], cfg['units'], cfg['volume'], cfg['diameter_mm'])
                self._logger.log(pid, 'PARALLEL DONE')
            except Exception as e:
                errors[pid] = str(e)
                self._logger.log(pid, 'PARALLEL ERROR', str(e))

        for cfg in configs:
            t = threading.Thread(target=_run, args=(cfg,))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise RuntimeError(f'Parallel run errors: {errors}')
    # ── CLEANUP ───────────────────────────────────────────

    def close_all(self):
        """Close all serial connections."""
        for pump_id, pump in self._pumps.items():
            try:
                pump.close()
            except Exception:
                pass
        for port, network in self._networks.items():
            try:
                network.close()
            except Exception:
                pass
        self._logger.log('ALL', 'CLOSED')

