# Pump Agent — Iteration Progress Log

## Current status (as of last run)

| Pump | Result | Score |
|------|--------|-------|
| harvard_elite | PASS | 6/6 |
| new_era_0 | PASS | 7/7 (stable; WDR occasionally fails on bad EMI runs) |
| new_era_1 | HARD FAIL | 0/1 — hardware issue |

---

## What is fixed and stable

### harvard_elite (COM6)
All 6 tests pass consistently every run. No changes needed.

### new_era_0 (COM7, addr 0) — all 7 tests passing
- **Firmware** — passes reliably
- **Idle status** — passes reliably
- **Parameters** (dia/rate/vol readback) — passes reliably
- **Direction INF** — passes reliably
- **Direction WDR** — passes most runs; occasionally fails when motor reversal EMI is exceptionally heavy
- **OOR error** — passes (fallback: checks pump alarm state if rate response is corrupted)
- **Motion** — passes reliably

---

## Root cause diagnosis

### RS-232 bus noise on COM7
The NE-4002X daisy-chain produces intermittent garbage bytes on the RS-232 bus.
The garbage is **non-deterministic** and correlated with:
- Motor running (EMI from stepper motor energization)
- Motor reversal (direction change generates a transient noise burst)
- First few commands after connect (bus not yet stable)

Key observations:
- `?` (0x3F) is often received as `>` (0x3E) — single-bit RS-232 error
- Status byte (I/W/S/A) is sometimes corrupted to an unrecognized character
- Garbage often has no ETX (`\x03`), causing `_read_until_etx` to time out

### addr 1 — hardware dead
All commands (`1VER\r`, `01VER\r`) return empty (`b''`). No response whatsoever.
This is a physical hardware issue: cable, connector, or pump address setting.
Software cannot fix it.

---

## All driver/agent changes made

### new_era.py
1. `_parse`: uses `rfind(b'\x03')` + `rfind(b'\x02', 0, etx_idx)` to extract the LAST complete STX-ETX frame, discarding garbage that precedes the real response
2. `_read_until_etx`: accumulate-all approach (not STX-gated); serial timeout changed from 2s → 0.2s so deadline is tracked accurately
3. `_send`: added `timeout=1.5` parameter, passed through to `_read_until_etx`; enables short-timeout polling from pump_agent
4. `_send`: `reset_input_buffer()` before every write — clears EMI garbage accumulated between commands (key fix for direction/motion tests)
5. `_send`: removed `time.sleep(0.1)` — read loop handles timing natively, saves ~100ms per command
6. `STATUS_ALARM`: corrected from `'?'` to `'A'`
7. `RATE_UNITS`: removed duplicate with MM/MH; kept only UM/UH (hardware only accepts microliter units)
8. `NewEraNetwork.__init__`: serial timeout changed from 2 → 0.2

### pump_agent.py
1. `_query_with_retry`: helper for retrying a query until validate passes; used throughout validate_new_era
2. `_query_with_retry`: default `max_tries` raised from 3 → 5; delay reduced from 0.25s → 0.1s
3. `validate_new_era` — initial state cleanup:
   - `pump.stop()` + 0.3s sleep at start
   - alarm clear if status is 'A'
   - adaptive warmup loop: up to 8 status queries until 3 consecutive valid responses
4. `firmware`: max_tries=5 (was 3)
5. `parameters`: max_tries=5 per readback
6. `idle_status`: removed redundant `pump.is_running()` round-trip; status already in hand
7. `_direction_check`: 
   - 3s polling loop (was 2s)
   - 0.15s post-run settle before first poll — lets motor-start EMI transient die
   - 0.8s motor settle after stop (was 0.5s)
   - short-timeout 0.4s poll using `pump._send('', timeout=0.4)` for more attempts
8. `direction_inf/wdr`: delegates to `_direction_check`
9. `oor_error`: rate response OOR check PLUS fallback alarm-state query if response is corrupted
10. `motion`: 3s polling loop (was 2s); 0.15s post-run settle; 0.8s after stop; alarm guard before run
11. Dead-pump fast-fail probe: short 0.4s `VER` probe before full validation — skips 40-60s of timeouts on addr 1

---

## What to try if WDR still fails consistently

If Direction WDR fails on multiple consecutive runs:
1. The motor reversal EMI is unusually heavy on this session
2. Unplug and replug the COM7 RS-232 cable, then re-run
3. Try running the agent again — noise is non-deterministic and often clears

## If addr 1 still gives HARD FAIL
This is a hardware issue. Check:
1. RJ11 cable between pump 0 and pump 1 is firmly seated
2. Pump 1 address is set to 1 (not 0 or other) — may need to set via front panel or `*ADR` command while connected directly
3. Pump 1 is powered on

---

## Files to NOT touch
- `pump_controller.py` — per CLAUDE.md, never edit to paper over driver bugs
- `harvard_elite.py` — always passes 6/6, no changes needed
- `debug_dir.py` — temporary debug file, safe to delete when done

## Files edited
- `new_era.py` — driver fixes
- `pump_agent.py` — validation + retry logic
