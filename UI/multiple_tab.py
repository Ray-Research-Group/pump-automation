"""Multiple tab: run several pumps in parallel via run_parallel."""

from tkinter import ttk

from config_row import PumpConfigRow
from state import SLOTS


class MultipleTab:
    def __init__(self, notebook, state, worker):
        self.state = state
        self.worker = worker
        self.frame = ttk.Frame(notebook, padding=12)

        ttk.Label(self.frame, text='Multiple Pumps (parallel)',
                  font=('TkDefaultFont', 13, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 8))

        self.rows = []
        for i, slot in enumerate(SLOTS):
            row = PumpConfigRow(self.frame, slot, state)
            row.grid(row=i + 1, column=0, sticky='w', pady=2)
            self.rows.append(row)

        self.run_btn = ttk.Button(self.frame, text='Run selected',
                                  command=self._run)
        self.run_btn.grid(row=len(SLOTS) + 1, column=0, sticky='w', pady=8)

        state.on_refresh(self.refresh)
        self.refresh()

    def refresh(self):
        for row in self.rows:
            row.refresh()

    def set_busy(self, busy):
        self.run_btn.configure(state='disabled' if busy else 'normal')

    def _run(self):
        try:
            configs = [c for c in (r.build_config() for r in self.rows)
                       if c is not None]
        except ValueError:
            self.worker.log('Check numeric fields on selected pumps.', 'error')
            return
        if not configs:
            self.worker.log('No pumps selected.', 'error')
            return

        ctrl = self.state.ctrl
        ids = ', '.join(c['pump_id'] for c in configs)
        self.worker.log(f'Running {len(configs)} pumps in parallel: {ids}')
        self.worker.run_async(lambda: ctrl.run_parallel(configs))
