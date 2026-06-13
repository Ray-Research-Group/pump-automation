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
import queue
from datetime import datetime
from harvard_elite import HarvardElite
from new_era import NewEraNetwork, NewEraPump


# ── PUMP WORKER THREAD ────────────────────────────────────────────────────────

class PumpWorker:
    """
    Processes setup tasks (set diameter, rate, volume) in a dedicated thread.
    Each pump gets its own worker to avoid blocking the main thread.
    """

    def __init__(self, pump_id, logger):
        self._pump_id = pump_id
        self._logger = logger
        self._queue = queue.Queue()
        self._thread = None
        self._stop_event = threading.Event()
        self._errors = []          # list of (label, message)
        self._errors_lock = threading.Lock()
        self._done_count = 0       # tasks fully processed (success or fail)
        self._submitted = 0        # tasks queued

    def start(self):
        """Start the worker thread."""
        self._thread = threading.Thread(target=self._run, daemon=False)
        self._thread.start()

    def _run(self):
        """Main worker loop — run queued callables until stop_event."""
        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if task is None:  # sentinel to stop
                break
            label, fn = task
            try:
                fn()
                self._logger.log(self._pump_id, f'{label} OK')
            except Exception as e:
                with self._errors_lock:
                    self._errors.append((label, str(e)))
                self._logger.log(self._pump_id, f'{label} ERROR', str(e))
            finally:
                self._done_count += 1

    def submit(self, label, fn):
        """Queue a labeled callable to run on the worker thread."""
        self._submitted += 1
        self._queue.put((label, fn))

    def wait_idle(self, timeout=None):
        """
        Block until every submitted task has finished processing.
        Raises RuntimeError if any task errored, TimeoutError if timeout expires.
        timeout: seconds to wait, or None for infinite (default).
        """
        deadline = None if timeout is None else (time.time() + timeout)
        while self._done_count < self._submitted:
            if deadline is not None and time.time() > deadline:
                raise TimeoutError(
                    f'{self._pump_id}: tasks did not finish within {timeout}s '
                    f'({self._done_count}/{self._submitted} done)'
                )
            time.sleep(0.02)
        self.raise_if_errors()

    def raise_if_errors(self):
        """Raise if any queued task failed since the last check, then clear."""
        with self._errors_lock:
            if self._errors:
                errs = self._errors
                self._errors = []
                detail = '; '.join(f'{label}: {msg}' for label, msg in errs)
                raise RuntimeError(f'{self._pump_id} setup failed — {detail}')

    def stop(self):
        """Stop the worker thread."""
        self._queue.put(None)
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)


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
    def wait_until_done(self, poll_interval=0.5, timeout=None): raise NotImplementedError
    def get_volume_dispensed(self): raise NotImplementedError
    def get_status(self): raise NotImplementedError
    def infuse(self, rate, units, volume, diameter_mm): raise NotImplementedError
    def withdraw(self, rate, units, volume, diameter_mm): raise NotImplementedError


# ── HARVARD WRAPPER ───────────────────────────────────────────────────────────

class HarvardWrapper(PumpInterface):
    """
    Wraps HarvardElite to match the unified PumpInterface.
    Normalizes unit strings to Harvard format.
    Uses a worker thread to decouple setup from execution.
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

    def __init__(self, port, pump_id, logger, baudrate=9600, timeout=2):
        self._pump = HarvardElite(port, baudrate, timeout)
        self._direction = 'infuse'
        self._worker = PumpWorker(pump_id, logger)
        self._worker.start()

    def _normalize_units(self, units):
        u = units.lower().replace(' ', '')
        result = self.RATE_UNITS.get(u)
        if result is None:
            raise ValueError(f'Invalid units: {units}. Valid: {list(self.RATE_UNITS.keys())}')
        return result

    def _start_run(self):
        """Dispatch the start command based on the configured direction."""
        if self._direction == 'infuse':
            return self._pump.infuse()
        elif self._direction == 'withdraw':
            return self._pump.withdraw()
        raise ValueError(f'Invalid direction: {self._direction}')

    def set_diameter(self, mm):
        self._worker.submit('set_diameter', lambda: self._pump.set_diameter(mm))

    def set_rate(self, rate, units='ml/min'):
        u = self._normalize_units(units)
        self._worker.submit('set_rate', lambda: self._pump.set_rate(rate, u))

    def set_withdraw_rate(self, rate, units='ml/min'):
        u = self._normalize_units(units)
        self._worker.submit('set_withdraw_rate', lambda: self._pump.set_withdraw_rate(rate, u))

    def set_volume(self, volume, units='ml'):
        self._worker.submit('set_volume', lambda: self._pump.set_volume(volume, units))

    def set_direction(self, direction):
        self._direction = direction.lower()

    def run(self):
        self._worker.submit('run', self._start_run)

    def stop(self):
        return self._pump.stop()

    def is_running(self):
        return self._pump.is_running()

    def wait_until_done(self, poll_interval=0.5, timeout=None):
        self._worker.wait_idle(timeout)
        return self._pump.wait_until_done(poll_interval, timeout)

    def get_volume_dispensed(self):
        return self._pump.get_volume_dispensed()

    def get_status(self):
        return self._pump.get_status()

    def _do_infuse(self, rate, units, volume, diameter_mm):
        self._pump.set_diameter(diameter_mm)
        self._pump.set_rate(rate, units)
        self._pump.set_volume(volume)
        self._direction = 'infuse'
        self._pump.infuse()

    def _do_withdraw(self, rate, units, volume, diameter_mm):
        self._pump.set_diameter(diameter_mm)
        self._pump.set_withdraw_rate(rate, units)
        self._pump.set_volume(volume)
        self._direction = 'withdraw'
        self._pump.withdraw()

    def infuse(self, rate, units, volume, diameter_mm):
        u = self._normalize_units(units)
        self._worker.submit('infuse', lambda: self._do_infuse(rate, u, volume, diameter_mm))
        self.wait_until_done()

    def withdraw(self, rate, units, volume, diameter_mm):
        u = self._normalize_units(units)
        self._worker.submit('withdraw', lambda: self._do_withdraw(rate, u, volume, diameter_mm))
        self.wait_until_done()

    def close(self):
        self._worker.stop()
        self._pump.close()


# ── NEW ERA WRAPPER ───────────────────────────────────────────────────────────

class NewEraWrapper(PumpInterface):
    """
    Wraps NewEraPump to match the unified PumpInterface.
    Uses a worker thread to decouple setup from execution.
    """

    def __init__(self, pump: NewEraPump, pump_id, logger):
        self._pump = pump
        self._worker = PumpWorker(pump_id, logger)
        self._worker.start()

    def set_diameter(self, mm):
        self._worker.submit('set_diameter', lambda: self._pump.set_diameter(mm))

    def set_rate(self, rate, units='ml/hr'):
        self._worker.submit('set_rate', lambda: self._pump.set_rate(rate, units))

    def set_volume(self, volume, units='ml'):
        # Driver expects µL and takes a single arg. Convert mL here.
        volume_ul = volume * 1000 if units.lower() == 'ml' else volume
        self._worker.submit('set_volume', lambda: self._pump.set_volume(volume_ul))

    def set_direction(self, direction):
        self._worker.submit('set_direction', lambda: self._pump.set_direction(direction))

    def run(self):
        self._worker.submit('run', lambda: self._pump.run())

    def stop(self):
        return self._pump.stop()

    def is_running(self):
        return self._pump.is_running()

    def wait_until_done(self, poll_interval=0.5, timeout=None):
        self._worker.wait_idle(timeout)
        return self._pump.wait_until_done(poll_interval, timeout)

    def get_volume_dispensed(self):
        return self._pump.get_volume_dispensed()

    def get_status(self):
        return self._pump.get_status()

    def infuse(self, rate, units, volume, diameter_mm):
        # Driver's infuse() runs the full sequence and converts mL->µL internally.
        self._worker.submit(
            'infuse',
            lambda: self._pump.infuse(rate, units, volume, diameter_mm)
        )
        self.wait_until_done()

    def withdraw(self, rate, units, volume, diameter_mm):
        self._worker.submit(
            'withdraw',
            lambda: self._pump.withdraw(rate, units, volume, diameter_mm)
        )
        self.wait_until_done()

    def close(self):
        self._worker.stop()


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
        wrapper = HarvardWrapper(port, pump_id, self._logger, baudrate)
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
        wrapper = NewEraWrapper(pump, pump_id, self._logger)
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

    def wait_until_done(self, pump_id, poll_interval=0.5, timeout=None):
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

    def wait_until_all_done(self, poll_interval=0.5, timeout=None):
        """Block until all pumps have stopped."""
        self._logger.log('ALL', 'WAITING FOR ALL TO FINISH')
        start = time.time()
        while any(p.is_running() for p in self._pumps.values()):
            if timeout is not None and time.time() - start > timeout:
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

    def release_all(self):
        """Close every pump and serial network and forget them.

        Frees the COM ports so another process (e.g. a UI-launched script)
        can open them. Re-register pumps afterwards with add_harvard /
        add_new_era.
        """
        for pump_id, pump in list(self._pumps.items()):
            try:
                pump.close()
            except Exception:
                pass
        self._pumps.clear()
        for port, network in list(self._networks.items()):
            try:
                network.close()
            except Exception:
                pass
        self._networks.clear()
        self._logger.log('ALL', 'RELEASED')

    def close_all(self):
        """Close all serial connections and stop worker threads."""
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

