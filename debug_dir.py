"""
Debug: instrument _read_until_etx to trace every byte received.
"""
import sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from new_era import NewEraNetwork, NewEraPump

# Instrument _read_until_etx to log every byte
original_retx = NewEraPump._read_until_etx

def debug_retx(self, timeout=3.0):
    deadline = time.time() + timeout
    buf = b''
    stx_seen = False
    t0 = time.time()
    while time.time() < deadline:
        n = self.ser.in_waiting
        chunk = self.ser.read(n if n else 1)
        dt = time.time() - t0
        if chunk:
            print(f'      +{dt:.3f}s  in_waiting={n}  chunk={chunk!r}  stx_seen={stx_seen}')
        if not chunk:
            continue
        for bv in chunk:
            if not stx_seen:
                if bv == 0x02:
                    stx_seen = True
                    buf = bytes([bv])
            else:
                buf += bytes([bv])
                if bv == 0x03:
                    print(f'      +{time.time()-t0:.3f}s  ETX found, returning buf={buf!r}')
                    return buf
    print(f'      +{time.time()-t0:.3f}s  TIMEOUT, buf={buf!r}')
    return buf

NewEraPump._read_until_etx = debug_retx

net = NewEraNetwork('COM7', 19200)
pump = net.add_pump(0)

for label, cmd in [
    ('alarm_check get_status', ''),
    ('firmware VER', 'VER'),
    ('idle_status get_status', ''),
]:
    print(f'=== {label} ===')
    r = pump._send(cmd)
    print(f'  result: status={r["status"]!r}  data={r["data"]!r}')
    time.sleep(0.1)

net.close()
