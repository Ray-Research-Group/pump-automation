# Ray Research Lab - Syringe Pump Automation

Control software for coordinated multi-pump experiments. Runs Harvard Apparatus and New Era pumps together from a single UI or Python script.

---

## Hardware Setup

Plug in all three pumps before launching the software.

| Pump | Model | Connection |
|------|-------|------------|
| pump_a | Harvard Apparatus Pump 11 Elite | USB to COM6 |
| pump_b | New Era NE-4002X (address 0) | RS-232 RJ11 to COM7 |
| pump_c | New Era NE-4002X (address 1) | RS-232 RJ11 to COM7 (daisy chained) |

The two New Era pumps share a single COM7 cable via daisy chain. Each pump has its own address set on the hardware (0 and 1). The Harvard connects separately on COM6 via USB.

---

## Quickstart (Windows)

Double-click `run.bat`. It pulls the latest code from GitHub, sets up the Python environment on first run, and opens the UI.

That's it. No terminal needed.

---

## First Run

On first launch, `run.bat` will create a `.venv` folder and install dependencies. This takes about a minute. Every subsequent launch is instant.

---

## Using the UI

### 1. Setup tab

Connect each pump before running anything.

- Pump A: type Harvard, port COM6
- Pump B: type New Era, port COM7, address 0
- Pump C: type New Era, port COM7, address 1

Click **Connect** on each row. The status turns green when the pump responds.

### 2. Manual tab

Run one or more pumps immediately with fixed settings. Set diameter, rate, volume, and direction for each pump, then hit **Run**.

### 3. Orchestrate tab

Paste or load a Python script and hit **Run script**. The UI releases its COM port connections, runs the script as a subprocess, streams its output into the log, then reconnects the pumps when it finishes.

**Load** opens a file browser pointed at `protocols/` where saved experiment scripts live.

**Insert template** drops in a ready-to-edit script skeleton.

**LLM prompt** opens a popup with the full API context. Copy it and paste into any LLM (ChatGPT, Claude, etc.) to generate a protocol script, then paste the result into the editor and run it.

**STOP ALL** at the bottom kills any running script, reconnects the pumps, and sends a stop command to all hardware.

---

## Writing Experiment Scripts

Scripts run exactly like `python script.py` from the repo root. They open their own controller and COM ports.

```python
import sys
sys.path.insert(0, 'src')

import signal
from pump_controller import PumpController

ctrl = None

def signal_handler(signum, frame):
    print('\n[KEYBOARD INTERRUPT] Stopping all pumps...')
    if ctrl:
        ctrl.stop_all()
        ctrl.close_all()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

ctrl = PumpController(log_file='logs/experiment.log')

ctrl.add_harvard('pump_a', port='COM6')
ctrl.add_new_era('pump_b', port='COM7', address=0)
ctrl.add_new_era('pump_c', port='COM7', address=1)

try:
    ctrl.run_parallel([
        {'pump_id': 'pump_a', 'rate': 15, 'units': 'ul/min', 'volume': 1.0, 'diameter_mm': 12.36, 'direction': 'infuse'},
        {'pump_id': 'pump_b', 'rate': 10, 'units': 'ul/min', 'volume': 1.0, 'diameter_mm': 12.36, 'direction': 'infuse'},
        {'pump_id': 'pump_c', 'rate': 10, 'units': 'ul/min', 'volume': 1.0, 'diameter_mm': 12.36, 'direction': 'infuse'},
    ])

except Exception as e:
    print(f'Error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()
```

Save finished scripts to `protocols/` so they appear in the Load dialog.

---

## Rate Limits

The New Era is a microfluidic pump. Its max rate at a 12.36 mm syringe is **~0.265 mL/min**. The Harvard at the same diameter can do up to **~19 mL/min**. The software will reject out-of-range rates with a clear error before anything reaches the hardware.

| Syringe | Diameter (mm) | Harvard max | New Era max |
|---------|---------------|-------------|-------------|
| BD 1 mL | 4.70 | 0.001 mL/min | 0.038 mL/min |
| BD 5 mL | 12.00 | 18.3 mL/min | 0.249 mL/min |
| BD 10 mL | 14.43 | 26.0 mL/min | 0.361 mL/min |
| BD 60 mL | 26.59 | 88.4 mL/min | 1.226 mL/min |

New Era single dispense is also capped at 9999 µL (~10 mL) by firmware. Volumes above that need continuous mode or repeated dispenses.

---

## Logs

All experiment logs write to `logs/experiment.log`. The file appends across runs so you have a full session history.

---

## Manual Python Launch

```bash
cd pump-automation
.venv\Scripts\activate
python UI/app.py
```
