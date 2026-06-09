"""
New Era Pump Systems NE-4002X Driver
Supports single pump and multi-pump network (up to 100 pumps).
Uses Basic communications mode (not Safe mode).
Protocol: ASCII commands terminated with CR, responses wrapped in STX/ETX.
"""

import serial
import time
import threading


def _fmt_number(value):
    """
    Format a number for New Era commands. Firmware accepts at most 4 significant
    figures and rejects trailing-zero floats like '10760.0' with ?OOR/?NA.
    Emits an integer string when the value is whole, else 4 sig figs.
    """
    if value == int(value):
        return str(int(value))
    return f'{value:.4g}'


class NewEraPump:
    """
    Driver for a single New Era pump on a network.
    All commands are prefixed with the pump address.
    """

    # Status characters returned in response
    STATUS_INFUSING  = 'I'
    STATUS_WITHDRAW  = 'W'
    STATUS_STOPPED   = 'S'
    STATUS_PAUSED    = 'P'
    STATUS_PURGING   = 'X'
    STATUS_ALARM     = 'A'

    def __init__(self, ser, address=0, lock=None):
        self.ser = ser
        self.address = address
        self._lock = lock or threading.RLock()

    def _send(self, cmd, timeout=1.5):
        with self._lock:
            self.ser.reset_input_buffer()
            full_cmd = f'{self.address}{cmd}\r'.encode()
            self.ser.write(full_cmd)
            raw = self._read_until_etx(timeout=timeout)
        return self._parse(raw)

    def _read_until_etx(self, timeout=1.5):
        """
        Read bytes until ETX (0x03) is found or timeout expires.
        Accumulates everything — garbage bytes that arrive before the real
        response are included; _parse extracts the last STX-ETX pair via rfind.
        Serial read timeout is set short (0.2 s) so the deadline is tracked
        accurately rather than blocked inside a 2-second read(1) call.
        """
        buf = b''
        deadline = time.time() + timeout
        while time.time() < deadline:
            n = self.ser.in_waiting
            if n:
                buf += self.ser.read(n)
            else:
                b = self.ser.read(1)
                if b:
                    buf += b
            if b'\x03' in buf:
                break
        return buf

    def _parse(self, raw):
        """
        Parse raw bytes from pump.
        Returns dict with keys: status, data, alarm, raw

        Garbage bytes often arrive on the bus immediately after a prior command's
        clean response, contaminating the next read.  We isolate the LAST complete
        STX…ETX frame in the buffer, which is always the real pump reply.
        rfind guarantees we pick the real STX even when garbage contains 0x02.
        """
        if not raw:
            return {'status': None, 'data': '', 'alarm': False, 'raw': raw}

        # Extract last complete STX...ETX frame
        etx_idx = raw.rfind(b'\x03')
        if etx_idx != -1:
            stx_idx = raw.rfind(b'\x02', 0, etx_idx)
            frame = raw[stx_idx + 1:etx_idx] if stx_idx != -1 else raw[:etx_idx]
        else:
            frame = raw

        text = frame.decode(errors='replace').replace('\x00', '').strip()

        # Alarm format: A?<alarm_type>
        alarm = 'A?' in text

        # Extract status character — comes after address digits
        status = None
        data = ''
        try:
            i = 0
            while i < len(text) and text[i].isdigit():
                i += 1
            if i < len(text):
                status = text[i]
                data = text[i + 1:].strip()
        except Exception:
            pass

        return {
            'status': status,
            'data': data,
            'alarm': alarm,
            'raw': raw
        }

    # ── CONFIGURATION ────────────────────────────────────

    def set_diameter(self, mm):
        """Set syringe inside diameter in mm."""
        return self._send(f'DIA {mm}')

    def get_diameter(self):
        return self._send('DIA')

    RATE_UNITS = {
        'ul/min': 'UM',
        'ml/min': 'UM',  # convert ml to ul
        'ul/hr':  'UH',
        'ml/hr':  'UH',  # convert ml to ul
    }

    def set_rate(self, rate, units='ul/hr'):
        units_lower = units.lower()
        unit_code = self.RATE_UNITS.get(units_lower)
        if unit_code is None:
            raise ValueError(f'Invalid units: {units}')
        
        # Convert mL to uL
        if units_lower in ('ml/min', 'ml/hr'):
            rate = rate * 1000

        return self._send(f'RAT {_fmt_number(rate)} {unit_code}')

    def get_rate(self):
        return self._send('RAT')

    def set_volume_units(self, units):
        """Set volume units for all phases. units: 'ml' or 'ul'."""
        code = 'ML' if units.lower() == 'ml' else 'UL'
        return self._send(f'VOL {code}')

    def set_volume(self, volume_ul):
        with self._lock:
            self.ser.reset_input_buffer()
            self.ser.write(f'{self.address}VOL UL\r'.encode())
            self._read_until_etx()
            self.ser.write(f'{self.address}VOL {_fmt_number(volume_ul)}\r'.encode())
            raw = self._read_until_etx()
        return self._parse(raw)

    def get_volume(self):
        return self._send('VOL')

    def set_direction(self, direction):
        """
        Set pumping direction.
        direction: 'infuse' or 'withdraw'
        """
        d = direction.lower()
        if d == 'infuse':
            return self._send('DIR INF')
        elif d == 'withdraw':
            return self._send('DIR WDR')
        else:
            raise ValueError("direction must be 'infuse' or 'withdraw'")

    def get_direction(self):
        return self._send('DIR')

    def set_address(self, address):
        """Set pump network address (0-99). Requires *ADR system command."""
        result = self._send(f'*ADR {address}')
        self.address = address
        return result

    def set_baud(self, baud):
        """Set baud rate. Valid: 300, 1200, 2400, 9600, 19200."""
        return self._send(f'*ADR {self.address} B {baud}')

    # ── OPERATION ────────────────────────────────────────

    def run(self):
        """Start the pumping program."""
        return self._send('RUN')

    def stop(self):
        """Stop/pause the pumping program."""
        return self._send('STP')

    def purge(self):
        """Start purge at max speed."""
        return self._send('PUR')

    # ── STATUS ───────────────────────────────────────────

    def get_status(self):
        """Query pump status. Returns parsed response dict."""
        return self._send('')

    def is_running(self):
        """True if pump is actively infusing or withdrawing."""
        r = self.get_status()
        return r['status'] in (self.STATUS_INFUSING, self.STATUS_WITHDRAW, self.STATUS_PURGING)

    def is_alarmed(self):
        """True if pump is in alarm state."""
        r = self.get_status()
        return r['alarm'] or r['status'] == self.STATUS_ALARM

    def get_volume_dispensed(self):
        """Query infused and withdrawn volumes."""
        return self._send('DIS')

    def clear_volume_dispensed(self, direction='both'):
        """
        Clear volume dispensed counters.
        direction: 'infuse', 'withdraw', or 'both'
        """
        if direction == 'infuse':
            return self._send('CLD INF')
        elif direction == 'withdraw':
            return self._send('CLD WDR')
        else:
            self._send('CLD INF')
            return self._send('CLD WDR')

    def get_firmware(self):
        """Query firmware version."""
        return self._send('VER')

    # ── BLOCKING WAIT ────────────────────────────────────
    def wait_until_done(self, poll_interval=0.2, timeout=300):
        start = time.time()
        time.sleep(0.5)  # give motor time to actually start before first poll
        while True:
            r = self.get_status()
            status = r['status']
            if status not in (self.STATUS_INFUSING, self.STATUS_WITHDRAW, self.STATUS_PURGING):
                # Only exit if we've been running long enough to be credible
                elapsed = time.time() - start
                if elapsed > 1.0:
                    break
            if time.time() - start > timeout:
                raise TimeoutError(f'Pump {self.address} did not finish within {timeout}s')
            if self.is_alarmed():
                raise RuntimeError(f'Pump {self.address} alarm detected')
            time.sleep(poll_interval)

    # ── CONVENIENCE ──────────────────────────────────────
    def _ensure_stopped(self):
        self.get_status()
        self._send('STP')
        time.sleep(0.15)
        self._send('STP')
        time.sleep(0.15)
        self._send('VOL UL')  # force µL regardless of stale state

    def infuse(self, rate, units, volume, diameter_mm):
        self._ensure_stopped()
        self.set_diameter(diameter_mm)
        self._send('VOL UL')          # re-lock after diameter resets units
        self.set_direction('infuse')
        self.set_rate(rate, units)
        self.set_volume(volume * 1000)  # convert mL to µL
        self.run()
        self.wait_until_done()

    def withdraw(self, rate, units, volume, diameter_mm):
        self._ensure_stopped()
        self.set_diameter(diameter_mm)
        self._send('VOL UL')          # missing — diameter resets units
        self.set_direction('withdraw')
        self.set_rate(rate, units)
        self.set_volume(volume * 1000)  # missing — needs mL -> µL conversion
        self.run()
        self.wait_until_done()


class NewEraNetwork:
    """
    Manages a network of New Era pumps on a single serial port.
    All pumps share one serial connection, addressed individually.
    """

    def __init__(self, port, baudrate=19200, timeout=0.2):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=timeout
        )
        self._lock = threading.RLock()
        time.sleep(0.3)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(0.1)
        self.ser.write(b'0\r')   # flush phantom byte
        time.sleep(0.2)
        self.ser.read_all()
        self.pumps = {}


    def add_pump(self, address):
        """Add a pump at the given address to the network."""
        pump = NewEraPump(self.ser, address, lock=self._lock)
        self.pumps[address] = pump
        return pump

    def get_pump(self, address):
        return self.pumps[address]

    def stop_all(self):
        """Stop all pumps on the network."""
        for pump in self.pumps.values():
            pump.stop()

    def run_all(self):
        """Start all pumps simultaneously."""
        for pump in self.pumps.values():
            pump.run()

    def wait_until_all_done(self, poll_interval=0.5, timeout=300):
        """Block until all pumps have stopped."""
        start = time.time()
        while any(p.is_running() for p in self.pumps.values()):
            if time.time() - start > timeout:
                raise TimeoutError('Not all pumps finished within timeout')
            time.sleep(poll_interval)

    def close(self):
        self.ser.close()


if __name__ == '__main__':
    # Quick connection test — change port as needed
    PORT = 'COM5'

    network = NewEraNetwork(PORT, baudrate=19200)
    pump0 = network.add_pump(0)

    r = pump0.get_firmware()
    print('Firmware:', r)

    r = pump0.get_status()
    print('Status:', r)

    network.close()