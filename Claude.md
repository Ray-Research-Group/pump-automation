# Syringe Pump Automation — Claude Code Context

## Project
Lab automation system for syringe pump control.
Path: `C:\Users\RayResearchLab\Documents\Ray_Research_Lab\Syringe_Automation`
Python venv: `.venv` — always activate before running anything.

## Architecture

```
harvard_elite.py       # Harvard Apparatus Pump 11 Elite driver
new_era.py             # New Era NE-4002X driver + network class
pump_controller.py     # Unified abstraction over both drivers (per-pump worker threads)
orchestrate.py         # Experiment execution target — LLM-generated code goes here
test.py                # New Era address scanner on COM7 (addresses 0-9)
debug_dir.py           # Direction/serial debug scratch script
llms.txt               # Experiment programming interface for external LLMs
Harvard.txt            # Harvard Pump 11 Elite command reference manual
NE4000x.txt            # New Era NE-4002X command reference manual
```

## Hardware

| Pump | Model | Port | Address | Protocol |
|------|-------|------|---------|----------|
| harvard_elite | Harvard Apparatus Pump 11 Elite I/W Single | COM6 | N/A | USB CDC, 9600 baud |
| new_era_0 | New Era NE-4002X firmware 4.670 | COM7 | 0 | RS-232 RJ11, 19200 baud |
| new_era_1 | New Era NE-4002X | COM7 | 1 | RS-232 RJ11, 19200 baud (daisy chained) |

New Era pumps share COM7 via daisy chain. Address is set on each pump individually.

## Known Hardware Quirks — READ BEFORE TOUCHING DRIVERS

- **New Era only accepts microliter rate units** (`UM`, `UH`) — never `MM` or `MH`. The driver auto-converts mL to uL before sending.
- **New Era alarm state** (`A?R`) must be cleared by sending an empty status query (`''`) before any other command will work.
- **New Era response format**: `\x02<address><status>[data]\x03` — STX/ETX wrapped, strip before parsing.
- **Harvard idle prompt**: `\n:` — the colon is the ready signal.
- **Harvard `T*`**: target reached — clear with `ctvolume` before next run.
- **New Era `?OOR`**: rate out of range for current syringe diameter — check diameter is set first.
- **Port locking**: only one process can hold a COM port. Kill all Python processes before opening a new connection: `taskkill /F /IM python.exe`

## Workflow

### Scanning the New Era network
```bash
python test.py
```
Probes COM7 addresses 0-9 and prints which addresses return a real firmware
string. Use this to confirm the daisy-chained pumps respond and to catch
address conflicts before running an experiment.

### Driver iteration — HOW TO FIX FAILURES
When a pump misbehaves:

1. Reproduce against hardware with `test.py` (New Era) or a short script
2. Check the command reference (`Harvard.txt` or `NE4000x.txt`) for the exact protocol
3. Edit the relevant driver (`harvard_elite.py` or `new_era.py`)
4. Re-run the reproduction
5. Repeat until it passes

IMPORTANT: Never edit `pump_controller.py` to paper over driver bugs. Fix the driver.

### Running an experiment
Paste LLM-generated code into `orchestrate.py`, then:
```bash
python orchestrate.py
```
The controller gives each pump its own worker thread for setup. Setup errors
(bad rate, `?OOR`, etc.) surface as a `RuntimeError` from `wait_until_done` /
`run_parallel` rather than being swallowed.

## Python Environment

```bash
# Activate venv (Windows SSH)
.venv\Scripts\activate

# Install deps
pip install pyserial
```

## Code Style

- No print statements in drivers — drivers return parsed dicts, callers handle display
- Every serial write must have a corresponding read — never fire and forget
- All timeouts explicit — never block indefinitely
- Retry and threading logic live in `pump_controller.py`, not in drivers
- Driver methods return raw parsed response dicts — transformation happens in controller