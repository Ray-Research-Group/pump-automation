"""Orchestrate tab: a dynamic stack of steps that run top-to-bottom.

Each step is a parallel group (1-3 slots). run_parallel blocks until a step's
pumps finish, so calling it per step in order gives sequential execution.
"""

import tkinter as tk
from tkinter import ttk

from config_row import PumpConfigRow
from state import SLOTS


class Step:
    def __init__(self, parent, state, index):
        self.state = state
        self.frame = ttk.LabelFrame(parent, padding=8)
        self.label = tk.StringVar(value=f'Step {index}')

        head = ttk.Frame(self.frame)
        head.grid(row=0, column=0, sticky='w')
        ttk.Label(head, text='Label').grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(head, textvariable=self.label, width=18).grid(row=0, column=1)

        # controls (wired by the tab after creation)
        self.up_btn = ttk.Button(head, text='↑', width=3)
        self.down_btn = ttk.Button(head, text='↓', width=3)
        self.del_btn = ttk.Button(head, text='Remove', width=8)
        self.up_btn.grid(row=0, column=2, padx=(12, 2))
        self.down_btn.grid(row=0, column=3, padx=2)
        self.del_btn.grid(row=0, column=4, padx=2)

        self.rows = []
        for i, slot in enumerate(SLOTS):
            row = PumpConfigRow(self.frame, slot, state)
            row.grid(row=i + 1, column=0, sticky='w', pady=1)
            self.rows.append(row)

    def refresh(self):
        for row in self.rows:
            row.refresh()

    def build_configs(self):
        return [c for c in (r.build_config() for r in self.rows) if c is not None]


class OrchestrateTab:
    def __init__(self, notebook, state, worker):
        self.state = state
        self.worker = worker
        self.frame = ttk.Frame(notebook, padding=12)
        self.steps = []
        self._counter = 0

        ttk.Label(self.frame, text='Orchestrate (sequential steps)',
                  font=('TkDefaultFont', 13, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 8))

        bar = ttk.Frame(self.frame)
        bar.grid(row=1, column=0, sticky='w')
        ttk.Button(bar, text='+ Add step', command=self.add_step).grid(
            row=0, column=0)
        self.run_btn = ttk.Button(bar, text='Run sequence', command=self._run)
        self.run_btn.grid(row=0, column=1, padx=8)

        # scrollable step list
        self.canvas = tk.Canvas(self.frame, height=420, highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient='vertical',
                              command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.grid(row=2, column=0, sticky='nsew', pady=8)
        scroll.grid(row=2, column=1, sticky='ns')
        self.frame.rowconfigure(2, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self.inner = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox('all')))

        state.on_refresh(self.refresh)
        self.add_step()

    def add_step(self):
        self._counter += 1
        step = Step(self.inner, self.state, self._counter)
        step.del_btn.configure(command=lambda s=step: self.remove_step(s))
        step.up_btn.configure(command=lambda s=step: self.move(s, -1))
        step.down_btn.configure(command=lambda s=step: self.move(s, +1))
        self.steps.append(step)
        self._relayout()

    def remove_step(self, step):
        step.frame.destroy()
        self.steps.remove(step)
        self._relayout()

    def move(self, step, delta):
        i = self.steps.index(step)
        j = i + delta
        if 0 <= j < len(self.steps):
            self.steps[i], self.steps[j] = self.steps[j], self.steps[i]
            self._relayout()

    def _relayout(self):
        for i, step in enumerate(self.steps):
            step.frame.grid(row=i, column=0, sticky='ew', pady=4)
            step.up_btn.configure(state='disabled' if i == 0 else 'normal')
            step.down_btn.configure(
                state='disabled' if i == len(self.steps) - 1 else 'normal')

    def refresh(self):
        for step in self.steps:
            step.refresh()

    def set_busy(self, busy):
        self.run_btn.configure(state='disabled' if busy else 'normal')

    def _run(self):
        try:
            plan = [(s.label.get(), s.build_configs()) for s in self.steps]
        except ValueError:
            self.worker.log('Check numeric fields in the steps.', 'error')
            return
        plan = [(label, cfgs) for label, cfgs in plan if cfgs]
        if not plan:
            self.worker.log('No steps with selected pumps.', 'error')
            return

        ctrl = self.state.ctrl
        worker = self.worker

        def task():
            for label, cfgs in plan:
                ids = ', '.join(c['pump_id'] for c in cfgs)
                worker.log(f'▶ {label}: {ids}')
                ctrl.run_parallel(cfgs)
                worker.log(f'✓ {label} done')

        self.worker.log(f'Running sequence of {len(plan)} steps.')
        self.worker.run_async(task)
