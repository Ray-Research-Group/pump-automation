# Syringe Pump Automation — Claude Code Context

## Project
Lab automation system for syringe pump control.
Path: `C:\Users\RayResearchLab\Documents\Ray_Research_Lab\Syringe_Automation`
Python venv: `.venv` — always activate before running anything.

## Architecture

```
harvard_elite.py       # Harvard Apparatus Pump 11 Elite driver
new_era.py             # New Era NE-4002X driver + network class
pump_controller.py     # Unified abstraction over both drivers
orchestrate.py         # Experiment execution target — LLM-generated code goes here
pump_agent.py          # Agentic network discovery and validation runner
llms.txt               # Experiment programming interface for external LLMs
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

### Running the agent
```bash
python pump_agent.py
```
Agent will:
1. Discover pumps on COM6 and COM7
2. Probe New Era addresses 0-9
3. Resolve address conflicts automatically
4. Validate all drivers with retry logic
5. Print final network table + save `agent_report.txt`

### Agentic failure resolution — HOW TO ITERATE
When `pump_agent.py` reports failures:

1. Read `agent_report.txt` for full detail
2. Identify failure category (see SPEC.md)
3. Edit the relevant driver (`harvard_elite.py` or `new_era.py`)
4. Re-run `pump_agent.py`
5. Repeat until all pumps pass

IMPORTANT: Never edit `pump_controller.py` to paper over driver bugs. Fix the driver.

### Running a specific test suite
```bash
python test_harvard_elite.py
python test_new_era.py
```

### Running an experiment
Paste LLM-generated code into `orchestrate.py`, then:
```bash
python orchestrate.py
```

## Pass Criteria

See `SPEC.md` for the full pass specification.
All pumps must pass before any experiment runs.

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
- Retry logic lives in `pump_agent.py`, not in drivers
- Driver methods return raw parsed response dicts — transformation happens in controller