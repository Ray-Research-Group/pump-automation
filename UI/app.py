"""Syringe Pump Automation — tkinter control panel.

Four tabs: Setup, Single, Multiple, Orchestrate. Drives the existing
PumpController. Launch with:  python UI/app.py
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

# Resolve repo root from this file and make src/ importable, like the scripts.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, 'src'))
sys.path.insert(0, _HERE)

from pump_controller import PumpController  # noqa: E402

from state import AppState  # noqa: E402
from worker import Worker  # noqa: E402
from setup_tab import SetupTab  # noqa: E402
from multiple_tab import MultipleTab  # noqa: E402
from orchestrate_tab import OrchestrateTab  # noqa: E402


class App:
    def __init__(self, root):
        self.root = root
        root.title('Ray Research Lab - Syringe Pump Automation')
        root.geometry('1000x760')

        self.ctrl = PumpController(
            log_file=os.path.join(_ROOT, 'experiment.log'))
        self.state = AppState(self.ctrl)
        self.worker = Worker()

        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=8, pady=(8, 0))

        self.setup = SetupTab(notebook, self.state, self.worker)
        self.multiple = MultipleTab(notebook, self.state, self.worker)
        self.orchestrate = OrchestrateTab(notebook, self.state, self.worker)

        notebook.add(self.setup.frame, text='Setup')
        notebook.add(self.multiple.frame, text='Manual')
        notebook.add(self.orchestrate.frame, text='Orchestrate')

        # Bottom bar: STOP + log pane
        bar = ttk.Frame(root, padding=8)
        bar.pack(fill='x')
        self.stop_btn = tk.Button(
            bar, text='STOP ALL', command=self.stop_all,
            bg='#c0392b', fg='white', font=('TkDefaultFont', 11, 'bold'),
            width=12)
        self.stop_btn.pack(side='left')

        log_frame = ttk.LabelFrame(root, text='Log', padding=4)
        log_frame.pack(fill='both', expand=False, padx=8, pady=(0, 8))
        self.log = tk.Text(log_frame, height=8, state='disabled', wrap='word')
        self.log.pack(side='left', fill='both', expand=True)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        log_scroll.pack(side='right', fill='y')
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.tag_configure('err', foreground='#c0392b')
        self.log.tag_configure('msg', foreground='black')

        self.run_tabs = [self.multiple, self.orchestrate]

        root.protocol('WM_DELETE_WINDOW', self.on_close)
        self._poll()

    def _poll(self):
        self.worker.drain(self.log, self._on_busy_change)
        self.root.after(100, self._poll)

    def _on_busy_change(self, busy):
        for tab in self.run_tabs:
            tab.set_busy(busy)

    def stop_all(self):
        if self.orchestrate.abort_if_running():
            return  # task thread handles reconnect + stop_all
        try:
            self.ctrl.stop_all()
            self.worker.log('STOP ALL sent.')
        except Exception as e:
            self.worker.log(f'Stop error: {e}', 'error')

    def on_close(self):
        try:
            self.ctrl.stop_all()
            self.ctrl.close_all()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
