"""Orchestrate tab: paste or load a Python script and run it as a subprocess.

Scripts run exactly like `python orchestrate.py` — they open their own
PumpController and COM ports. The UI releases its connections before launch
and reacquires them on exit. STOP kills the subprocess then reconnects and
stops the pumps.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SCRIPT_PATH = os.path.join(_ROOT, 'logs', '_ui_script.py')
_LLMS_PATH = os.path.join(_ROOT, 'llms.txt')

_TEMPLATE = """\
import sys
sys.path.insert(0, 'src')
from pump_controller import PumpController

ctrl = PumpController(log_file='logs/experiment.log')
ctrl.add_harvard('harvard_elite', port='COM6')
ctrl.add_new_era('new_era_0', port='COM7', address=0)

# protocol here

ctrl.stop_all()
ctrl.close_all()
"""


class OrchestrateTab:
    def __init__(self, notebook, state, worker):
        self.state = state
        self.worker = worker
        self.frame = ttk.Frame(notebook, padding=12)
        self._proc = None
        self._killed = False

        ttk.Label(self.frame, text='Orchestrate (script runner)',
                  font=('TkDefaultFont', 13, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))

        # button bar
        bar = ttk.Frame(self.frame)
        bar.grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Button(bar, text='Load…', command=self._load).grid(row=0, column=0)
        ttk.Button(bar, text='Save as…', command=self._save).grid(row=0, column=1, padx=4)
        ttk.Button(bar, text='Insert template', command=self._insert_template).grid(row=0, column=2)
        ttk.Button(bar, text='LLM prompt…', command=self._show_llm_prompt).grid(row=0, column=3, padx=(12, 0))
        self.run_btn = ttk.Button(bar, text='Run script', command=self._run)
        self.run_btn.grid(row=0, column=4, padx=(4, 0))

        # code editor
        editor_frame = ttk.Frame(self.frame)
        editor_frame.grid(row=2, column=0, sticky='nsew')
        self.editor = tk.Text(editor_frame, font=('Courier', 11), undo=True,
                              wrap='none', width=80, height=28)
        vscroll = ttk.Scrollbar(editor_frame, orient='vertical', command=self.editor.yview)
        hscroll = ttk.Scrollbar(editor_frame, orient='horizontal', command=self.editor.xview)
        self.editor.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.editor.grid(row=0, column=0, sticky='nsew')
        vscroll.grid(row=0, column=1, sticky='ns')
        hscroll.grid(row=1, column=0, sticky='ew')
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        self.frame.rowconfigure(2, weight=1)
        self.frame.columnconfigure(0, weight=1)

    # ── public API (called by app.py) ─────────────────────────────────────────

    def set_busy(self, busy):
        self.run_btn.configure(state='disabled' if busy else 'normal')

    def abort_if_running(self):
        proc = self._proc
        if proc and proc.poll() is None:
            self._killed = True
            proc.kill()
            self.worker.log('Killing running script...', 'error')
            return True
        return False

    # ── button handlers ───────────────────────────────────────────────────────

    def _load(self):
        path = filedialog.askopenfilename(
            initialdir=os.path.join(_ROOT, 'protocols'),
            filetypes=[('Python scripts', '*.py'), ('All files', '*.*')])
        if path:
            with open(path, 'r') as f:
                text = f.read()
            self.editor.delete('1.0', 'end')
            self.editor.insert('1.0', text)

    def _save(self):
        path = filedialog.asksaveasfilename(
            initialdir=os.path.join(_ROOT, 'protocols'),
            defaultextension='.py',
            filetypes=[('Python scripts', '*.py'), ('All files', '*.*')])
        if path:
            with open(path, 'w') as f:
                f.write(self.editor.get('1.0', 'end-1c'))

    def _insert_template(self):
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', _TEMPLATE)

    def _run(self):
        text = self.editor.get('1.0', 'end-1c').strip()
        if not text:
            self.worker.log('Script editor is empty.', 'error')
            return

        with open(_SCRIPT_PATH, 'w') as f:
            f.write(text)

        params = dict(self.state.conn_params)
        ctrl = self.state.ctrl
        worker = self.worker

        def task():
            self._killed = False
            ctrl.release_all()
            worker.log('COM ports released. Starting script...')

            try:
                proc = subprocess.Popen(
                    [sys.executable, '-u', _SCRIPT_PATH],
                    cwd=_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                self._proc = proc
                for line in proc.stdout:
                    worker.log(line.rstrip())
                rc = proc.wait()
            finally:
                self._proc = None

            if self._killed:
                worker.log('Script killed.', 'error')
            elif rc != 0:
                worker.log(f'Script exited with code {rc}.', 'error')
            else:
                worker.log('Script finished.')

            self._reconnect(params, ctrl, worker)

            if self._killed:
                try:
                    ctrl.stop_all()
                    worker.log('STOP ALL sent after kill.')
                except Exception as e:
                    worker.log(f'Stop error after kill: {e}', 'error')

        self.worker.run_async(task)

    def _show_llm_prompt(self):
        try:
            with open(_LLMS_PATH, 'r') as f:
                text = f.read()
        except Exception as e:
            self.worker.log(f'Could not read llms.txt: {e}', 'error')
            return

        win = tk.Toplevel(self.frame)
        win.title('LLM Prompt - paste into any LLM')
        win.geometry('700x540')

        box = tk.Text(win, font=('Courier', 10), wrap='word', padx=8, pady=8)
        scroll = ttk.Scrollbar(win, orient='vertical', command=box.yview)
        box.configure(yscrollcommand=scroll.set)
        box.insert('1.0', text)
        box.configure(state='disabled')
        box.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')

        def copy_all():
            win.clipboard_clear()
            win.clipboard_append(text)
            copy_btn.configure(text='Copied!')
            win.after(1500, lambda: copy_btn.configure(text='Copy all'))

        btn_bar = ttk.Frame(win)
        btn_bar.pack(side='bottom', fill='x', padx=8, pady=6)
        copy_btn = ttk.Button(btn_bar, text='Copy all', command=copy_all)
        copy_btn.pack(side='left')
        ttk.Button(btn_bar, text='Close', command=win.destroy).pack(side='right')

    def _reconnect(self, params, ctrl, worker):
        if not params:
            return
        worker.log('Reconnecting pumps...')
        for slot, (ptype, port, addr) in params.items():
            pump_id = self.state.pump_id(slot)
            try:
                if ptype == 'Harvard':
                    ctrl.add_harvard(pump_id, port=port)
                else:
                    ctrl.add_new_era(pump_id, port=port, address=addr)
                worker.log(f'Pump {slot} reconnected.')
            except Exception as e:
                worker.log(
                    f'Pump {slot} reconnect failed: {e}. Use Setup tab to reconnect.',
                    'error')
