# Pump Network Pass Specification

This is the ground truth for what "working" means.
`pump_agent.py` implements this spec. All failures must be resolved before experiments run.

---

## Pass Criteria Per Pump

Every registered pump must pass ALL of the following:

### 1. Connection
- [ ] COM port opens without error
- [ ] Port is not held by another process

### 2. Firmware
- [ ] Pump responds to firmware query within timeout
- [ ] Response contains expected model string
  - Harvard: response contains `ELITE`
  - New Era: response contains `NE`
- [ ] No alarm state on startup (or alarm clears automatically)

### 3. Idle Status
- [ ] Status query returns valid status character
  - Harvard: response contains `:`
  - New Era: status is `S` (stopped)
- [ ] `is_running()` returns `False` when idle

### 4. Parameter Set / Readback
Every parameter must round-trip correctly:

| Parameter | Set command | Readback must contain |
|-----------|------------|----------------------|
| Diameter | `set_diameter(14.43)` | `14.43` |
| Rate | `set_rate(500, 'ul/hr')` | `500` |
| Volume | `set_volume(0.5)` | `0.5` or `.500` |
| Direction infuse | `set_direction('infuse')` | `INF` |
| Direction withdraw | `set_direction('withdraw')` | `WDR` |

### 5. Error Handling
- [ ] Out-of-range rate returns error (not silent failure)
- [ ] Invalid unit strings raise `ValueError` in Python (not sent to pump)

### 6. Motion
- [ ] `run()` starts the pump (status changes to running)
- [ ] `stop()` halts the pump within 1 second
- [ ] `is_running()` accurately reflects pump state
- [ ] `wait_until_done()` blocks until pump stops

---

## Failure Categories

### Hard Failure — abort this pump, log, continue to next
- Port won't open
- No response after 3 retries
- Pump model string not recognized

### Soft Failure — agent must fix automatically and retry
| Symptom | Agent Action |
|---------|-------------|
| Alarm state (`A?R`) | Send empty status query to clear, retry |
| Null bytes in response | Flush buffer, retry |
| Garbage response | Flush buffer, sleep 0.5s, retry |
| Address conflict | Reassign conflicting pump to next free address |
| Port held by another process | `taskkill /F /IM python.exe`, retry |

### Test Failure — fix driver, re-run agent
| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Rate readback mismatch | Unit conversion wrong | Fix `set_rate()` in driver |
| Direction readback empty | Response format changed | Fix `_parse()` or `set_direction()` |
| Diameter readback garbage | Null byte in response | Fix `_parse()` to strip null bytes |
| `?OOR` on valid rate | Diameter not set first | Ensure diameter set before rate |
| `T*` on run | Previous target not cleared | Add `ctvolume` / `VOL 0` before run |

---

## Network Pass State

Final state must be:

```
PUMP                 PORT     ADDR   FIRMWARE                  RESULT
----------------------------------------------------------------------
harvard_elite        COM6     N/A    11 ELITE I/W Single 3.0.4 ✓ PASS (6/6)
new_era_0            COM7     0      NE4002XV4.670             ✓ PASS (7/7)
new_era_1            COM7     1      NE4002XV4.670             ✓ PASS (7/7)
```

Any `✗ FAIL` or `✗ NOT CONNECTED` blocks experiment execution.

---

## Agent Iteration Protocol

When Claude Code runs `pump_agent.py` and sees failures:

1. Read `agent_report.txt`
2. Classify each failure using the table above
3. For soft failures: fix in `pump_agent.py` retry logic
4. For test failures: fix in the relevant driver file
5. Re-run `pump_agent.py`
6. Repeat until network pass state is achieved
7. Do not mark complete until ALL pumps show `✓ PASS`

IMPORTANT: Never suppress a test to make it pass. Fix the underlying driver behavior.