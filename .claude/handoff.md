# Handoff — Pump Automation CLI

## Project
`/Users/danvu/Documents/Ray Research Lab/pump-automation`
Branch: `prod`

## What was built this session

Replaced `orchestrate.py` with an interactive CLI tool for manual pump control.

### CLI behavior
- On launch, connects pump_b (COM7, address 0) and pump_c (COM7, address 1). pump_a is not used.
- Loops forever prompting for input.
- **1**: pump_b infuses 1 µL, pump_c withdraws 1 µL simultaneously (balance +1)
- **2**: pump_c infuses 1 µL, pump_b withdraws 1 µL simultaneously (balance -1)
- Tracks a running `balance` (µL). Hard cap at ±19 µL — blocks the move and prints a message if limit reached.
- Rate: 38 µL/min on both pumps. Diameter: 12.36 mm. Increment: 1 µL (0.001 mL passed to controller).
- Ctrl+C triggers signal handler: stop_all → close_all → exit.

### Key implementation detail
`PumpController` takes volumes in mL. 1 µL = 0.001 mL. The constant `INCREMENT = 0.001` handles this.

## Hardware context
| Pump | Model | Port | Address |
|------|-------|------|---------|
| pump_b | New Era NE-4002X | COM7 | 0 |
| pump_c | New Era NE-4002X | COM7 | 1 |

New Era max rate at 12.36 mm: ~265 µL/min. 38 µL/min is well within range.
New Era single-dispense cap: 9999 µL (10 mL). 1 µL increments are far below this.

## Files changed
- `orchestrate.py` — full rewrite to CLI loop (see current file for full source)

## Reference files
- `llms.txt` — full API + hardware reference
- `CLAUDE.md` — project architecture, quirks, style rules
- `src/pump_controller.py` — unified controller (run_parallel, wait_until_done, etc.)
- `src/pump_limits.py` — rate/volume validation

## What's not done / possible next steps
- No persistence of balance across runs (resets to 0 on restart)
- No logging of individual moves to experiment.log (PumpController logs internally but balance state is not saved)
- Could add option 3 (e.g. emergency stop, status query, or reset balance)
- Could add configurable increment size at launch

## Suggested skills for next session
None required. This is a straightforward Python/serial project. If extending the CLI significantly, `/plan` mode may help structure changes.
