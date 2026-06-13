# Implementation Plan: Orchestrate Tab → Python Script Runner

**Status: PARTIALLY IMPLEMENTED — foundation done, UI rewrite not started.**
Read this whole file before touching anything. Decisions below were made with
Dan explicitly; do not relitigate them.

## Goal

Replace the Orchestrate tab's step-widget stack (`UI/orchestrate_tab.py`) with
a plain Python script runner: a text editor where you paste/load arbitrary
Python (typically LLM-generated, same contract as `orchestrate.py`), hit Run,
and the script executes while the UI stays alive with a working STOP button
and live log output.

## Locked-in design decisions

1. **Scripts run AS-IS, exactly like `python orchestrate.py`** (Dan chose this
   explicitly over an injected-`ctrl` API). Scripts create their own
   `PumpController`, do their own `sys.path.insert(0, 'src')`, open their own
   COM ports. Zero changes to llms.txt-generated code.
2. **Consequence — port ownership dance.** Only one process can hold a COM
   port (see CLAUDE.md). So the run flow is:
   - UI releases all serial connections (`ctrl.release_all()` — already added)
   - script runs as a **subprocess** (`[sys.executable, '-u', script_path]`,
     `cwd` = repo root) with stdout/stderr streamed into the UI log pane
   - on exit (normal or killed), UI reconnects pumps from saved params
3. **STOP semantics while a script runs:** kill the subprocess → reconnect
   pumps → `ctrl.stop_all()`. Killing the process does NOT stop the pumps —
   they run autonomously — hence the mandatory reconnect+stop.
4. **Setup-tab UI state is NOT touched during a run.** Slots stay shown as
   registered; the release/reconnect happens behind the scenes. Only if a
   reconnect FAILS do we log loudly (error level) and tell the user to use
   the Setup tab. (Avoids touching tkinter widgets from the worker thread.)
5. present llms.txt in orchestrate tab and instruct users on how to make a new custom script in natural language

## Already implemented (do not redo)

- `src/pump_controller.py` — `release_all()` added in the CLEANUP section:
  closes + clears `_pumps` and `_networks`, logs 'RELEASED'. This is what
  frees COM ports pre-run.
- `UI/state.py` — `AppState.conn_params = {}` added: maps
  `slot -> (ptype, port, addr)` (`addr` is `None` for Harvard, `int` for
  New Era).
- `UI/setup_tab.py` — `_connect()` now stores `conn_params[slot]` on success;
  `_disconnect()` pops it.

## Remaining work

### 1. Rewrite `UI/orchestrate_tab.py` (the main job)

Delete the `Step` class and step-stack machinery entirely (`PumpConfigRow` is
still used by `multiple_tab.py` — leave `config_row.py` alone). New
`OrchestrateTab` keeps the same constructor signature
`(notebook, state, worker)` so `app.py` wiring barely changes.

Widgets:
- Big `tk.Text` code editor (monospace, with scrollbar), undo enabled
- Buttons: **Load…** (filedialog → read into editor), **Save as…**,
  **Insert template**, **Run script**
- `set_busy(busy)` disables the Run button (keep — `app.py` calls it)

Template (starter inserted by button) mirrors orchestrate.py / llms.txt:

```python
import sys
sys.path.insert(0, 'src')
from pump_controller import PumpController

ctrl = PumpController(log_file='experiment.log')
ctrl.add_harvard('harvard_elite', port='COM6')
ctrl.add_new_era('new_era_0', port='COM7', address=0)

# protocol here

ctrl.stop_all()
ctrl.close_all()
```

Run flow (`_run`):
1. Get editor text; error-log and bail if empty.
2. Write it to `<repo_root>/_ui_script.py` (add `_ui_script.py` to
   `.gitignore` if one exists).
3. Snapshot `dict(state.conn_params)` BEFORE starting (it's read on the
   worker thread later).
4. `worker.run_async(task)` where `task` (worker thread):
   - `self._killed = False`
   - `ctrl.release_all()` + log it
   - `subprocess.Popen([sys.executable, '-u', _SCRIPT_PATH], cwd=_ROOT,
     stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)`; store in
     `self._proc`
   - stream `for line in proc.stdout: worker.log(line.rstrip())`
   - `rc = proc.wait()`; `self._proc = None` in a `finally`
   - log outcome: killed (error) / nonzero rc (error) / finished (info)
   - `self._reconnect(params)` — loop saved conn_params, call
     `ctrl.add_harvard` / `ctrl.add_new_era` per slot, log each success;
     on per-slot failure log error "use Setup tab" and continue
   - if `self._killed`: `ctrl.stop_all()` + log 'STOP ALL sent after kill.'

Abort hook (called from GUI thread):

```python
def abort_if_running(self):
    proc = self._proc
    if proc and proc.poll() is None:
        self._killed = True
        proc.kill()
        self.worker.log('Killing running script...', 'error')
        return True
    return False
```

Thread-safety notes: `worker.log` is queue-based and safe from any thread
(see `UI/worker.py`). Never call `state.mark_registered`/`fire_refresh` or
touch widgets from the task thread.

### 2. `UI/app.py` — wire STOP into the script runner

In `App.stop_all()`, before the existing `ctrl.stop_all()` path:

```python
def stop_all(self):
    if self.orchestrate.abort_if_running():
        return  # task thread handles reconnect + stop_all
    ...existing body...
```

Also update the module docstring tab description if it mentions steps.

### 3. Docs sync (CLAUDE.md rule: same-change updates)

- `CLAUDE.md`: update `orchestrate_tab.py` line in the architecture tree
  ("paste/run arbitrary Python scripts as subprocess; releases/reacquires
  COM ports; STOP kills + reconnects + stops"). Mention
  `PumpController.release_all()` where controller API is described.
- `src/PROGRESS.md`: session log entry.
- Optionally note in `llms.txt` that generated scripts can be pasted into
  the UI's Orchestrate tab unchanged.

### 4. Testing (needs the Windows lab machine — cannot be done in sandbox)

- Smoke: run UI, connect pumps in Setup, paste a trivial script
  (`print('hi')`, no pumps) → output appears in log, reconnect succeeds.
- Real: paste a short infuse script → pumps run, log streams.
- STOP mid-run: subprocess dies, pumps reconnect, pumps physically stop.
- Reconnect-failure path: unplug a pump mid-run, confirm loud error.
- Regression: Manual (multiple) tab still works after a script run.

## Known risks / gotchas

- **Kill→reopen race on Windows:** after `proc.kill()` the OS may take a
  beat to release COM handles. If reconnect throws 'access denied', add a
  short retry loop (e.g. 3 tries, 0.5 s apart) around the reconnect calls.
- New Era alarm state after an abrupt kill: driver already clears via empty
  status query on connect; if reconnects act weird, that's where to look.
- `worker.run_async` enforces one task at a time (`_busy`) — Run is
  inherently serialized, no extra guarding needed.
