import serial
import time

_VALID_UNITS = {'ul/min', 'ml/min', 'ul/hr', 'ml/hr', 'nl/min', 'pl/min'}


class HarvardElite:
    BAUD = 9600

    def __init__(self, port, baudrate=9600, timeout=2):
        self.port = port
        self._response_timeout = float(timeout)
        self._ser = serial.Serial(
            port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        self._direction = 'INF'
        time.sleep(0.2)
        self._ser.reset_input_buffer()

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()

    def _send(self, cmd):
        self._ser.reset_input_buffer()
        self._ser.write((cmd + '\r').encode('ascii'))
        return self._read_response()

    def _read_response(self):
        buf = b''
        deadline = time.time() + self._response_timeout
        while time.time() < deadline:
            n = self._ser.in_waiting
            if n:
                buf += self._ser.read(n)
            else:
                b = self._ser.read(1)
                if b:
                    buf += b
            # Harvard prompt always ends with ':'
            stripped = buf.rstrip(b'\r\n ')
            if stripped and stripped[-1:] == b':':
                break
        return buf.decode('ascii', errors='replace')

    def get_firmware(self):
        resp = self._send('ver')
        return {'raw': resp}

    def get_status(self):
        resp = self._send('')
        return {'raw': resp, 'running': self._check_running(resp)}

    def _check_running(self, resp):
        stripped = resp.strip()
        return '>' in stripped or '<' in stripped

    def is_running(self):
        resp = self._send('')
        return self._check_running(resp)

    def set_diameter(self, mm):
        self._send(f'diameter {mm}')
        readback = self._send('diameter')
        return {'readback': readback}

    def set_rate(self, rate, units):
        if units not in _VALID_UNITS:
            raise ValueError(f"Invalid units '{units}'. Valid: {sorted(_VALID_UNITS)}")
        self._send(f'irate {rate} {units}')
        readback = self._send('irate')
        return {'readback': readback}

    def set_withdraw_rate(self, rate, units):
        if units not in _VALID_UNITS:
            raise ValueError(f"Invalid units '{units}'. Valid: {sorted(_VALID_UNITS)}")
        self._send(f'wrate {rate} {units}')
        readback = self._send('wrate')
        return {'readback': readback}

    def set_volume(self, volume, units='ml'):
        self._send(f'tvolume {volume} {units}')
        readback = self._send('tvolume')
        return {'readback': readback}

    def set_direction(self, direction):
        if direction not in ('infuse', 'withdraw'):
            raise ValueError("direction must be 'infuse' or 'withdraw'")
        self._direction = 'INF' if direction == 'infuse' else 'WDR'
        # Harvard has no standalone direction command; direction is implicit in irun/wrun.
        # Query the relevant rate register to confirm pump is responsive.
        self._send('irate') if self._direction == 'INF' else self._send('wrate')
        return {'readback': self._direction}

    def get_direction(self):
        return {'readback': self._direction}

    def infuse(self):
        """Non-blocking: start infuse run."""
        self._direction = 'INF'
        resp = self._send('irun')
        return {'raw': resp}

    def withdraw(self):
        """Non-blocking: start withdraw run."""
        self._direction = 'WDR'
        resp = self._send('wrun')
        return {'raw': resp}

    def stop(self):
        resp = self._send('stp')
        return {'raw': resp}

    def clear_target_volume(self):
        resp = self._send('ctvolume')
        return {'raw': resp}

    def clear_volume(self):
        resp = self._send('cvolume')
        return {'raw': resp}

    def wait_until_done(self, poll_interval=0.5, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.is_running():
                return True
            time.sleep(poll_interval)
        return False

    def get_volume_dispensed(self):
        resp = self._send('ivolume')
        return {'raw': resp}
