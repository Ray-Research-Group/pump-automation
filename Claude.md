# Syringe Pump Automation — Claude Code Context

## Project
Lab automation system for syringe pump control.
Path: `C:\Users\RayResearchLab\Documents\Ray_Research_Lab\Syringe_Automation`
Python venv: `.venv` — always activate before running anything.

## Architecture

```
harvard_elite.py       # Harvard Apparatus Pump 11 Elite driver
new_era.py             # New Era NE-4002X driver + network class
pump_limits.py         # Diameter-based rate/volume limit checks for both pumps
pump_controller.py     # Unified abstraction over both drivers (per-pump worker threads)
orchestrate.py         # Experiment execution target — LLM-generated code goes here
test.py                # New Era address scanner on COM7 (addresses 0-9)
debug_dir.py           # Direction/serial debug scratch script
llms.txt               # Experiment programming interface for external LLMs
Harvard.txt            # Harvard Pump 11 Elite manual (spec table + Appendix A/B rate limits)
NE4002X.txt            # New Era NE-4002X rates + specs (the pump we actually have)
NE4000x.txt            # Generic NE-4000 manual — OVERSTATES range, do not trust limits
```

## Hardware

| Pump | Model | Port | Address | Protocol |
|------|-------|------|---------|----------|
| harvard_elite | Harvard Apparatus Pump 11 Elite I/W Single | COM6 | N/A | USB CDC, 9600 baud |
| new_era_0 | New Era NE-4002X firmware 4.670 | COM7 | 0 | RS-232 RJ11, 19200 baud |
| new_era_1 | New Era NE-4002X | COM7 | 1 | RS-232 RJ11, 19200 baud (daisy chained) |

New Era pumps share COM7 via daisy chain. Address is set on each pump individually.

## Known Hardware Quirks — READ BEFORE TOUCHING DRIVERS

- **New Era only accepts microliter units** (`UM`, `UH`, and µL volume) — never `MM`, `MH`, or mL. There is no working mL LED on firmware 4.670. The driver auto-converts mL to µL before sending.
- **New Era 4-digit field**: every numeric value is 4 digits + decimal. This caps a single "volume to be dispensed" at **9999 µL (~10 mL)** and means large µL rate/volume values silently overflow and get dropped if not pre-checked. Big volumes need continuous mode (`VOL 0`) + timed stop, or repeated dispenses.
- **New Era rate ceiling is diameter-dependent and LOW** — this is a microfluidic pump. Absolute max is **1226 µL/min** (1.226 mL/min, B-D 60 mL). At our 12.36 mm diameter the max is only **~265 µL/min (0.265 mL/min)**. mL/min-scale rates are out of range on this pump. See `pump_limits.py` / `NE4002X.txt`.
- **Harvard rate ceiling** comes from pusher travel (max 159 mm/min): at 12.36 mm that allows up to **~19 mL/min**. Much faster than the New Era at the same diameter — do not assume identical configs work on both.
- **New Era alarm state** (`A?R`) must be cleared by sending an empty status query (`''`) before any other command will work.
- **New Era response format**: `\x02<address><status>[data]\x03` — STX/ETX wrapped, strip before parsing.
- **Harvard idle prompt**: `\n:` — the colon is the ready signal.
- **Harvard `T*`**: target reached — clear with `ctvolume` before next run.
- **New Era `?OOR`**: rate out of range for current syringe diameter — check diameter is set first. `pump_limits.py` now catches most of these before they reach the pump.
- **Port locking**: only one process can hold a COM port. Kill all Python processes before opening a new connection: `taskkill /F /IM python.exe`

## Rate & Volume Limits — `pump_limits.py`

Both pumps compute flow as pusher velocity × syringe cross-sectional area, so
the achievable rate depends on diameter. `pump_limits.py` computes the real
limits and raises **loudly** (`RateOutOfRange` / `VolumeOutOfRange`, both
`ValueError` subclasses) before anything reaches the serial port. Previously
out-of-range values were silently mangled by the firmware.

- **Harvard**: pure formula from pusher travel rate (0.000153–159 mm/min × area).
  Validated against `Harvard.txt` Appendix B to 4 significant figures.
- **New Era**: per-diameter max-rate table parsed from `NE4002X.txt`, clamped to
  the 1226 µL/min absolute max; volume capped at 9999 µL.

How it wires in:
- Each driver tracks its last-set diameter (`set_diameter` stores `_diameter_mm`).
- `set_rate` / `set_withdraw_rate` convert the request to µL/min and check it.
- New Era `set_volume` checks the 9999 µL ceiling.
- Checks **fail open if diameter is unknown** (set diameter first, or you fall
  back to the pump's own `?OOR`). The composite `infuse`/`withdraw` always set
  diameter before rate, so they are covered.
- Errors raised in setup propagate through the worker thread and surface as a
  `RuntimeError` from `wait_until_done` / `run_parallel`.

To re-derive or extend the tables, the source data is in `Harvard.txt`
(Appendix A diameters, Appendix B rates) and `NE4002X.txt` (rate table).

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
2. Check the command reference (`Harvard.txt` or `NE4002X.txt`) for the exact protocol and limits
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
- Rate/volume limit math lives in `pump_limits.py` — drivers call it, do not inline limit constants
- Driver methods return raw parsed response dicts — transformation happens in controller
- Keep this CLAUDE.md in sync: update it in the same change whenever drivers, controller, limits, or files change