"""Single tab: run one pump (infuse or withdraw)."""

import tkinter as tk
from tkinter import ttk

from config_row import UNITS


class SingleTab:
    def __init__(self, notebook, state, worker):
        self.state = state
        self.worker = worker
        self.frame = ttk.Frame(notebook, padding=12)

        ttk.Label(self.frame, text='Single Pump',
                  font=('TkDefaultFont', 13, 'bold')).grid(
            row=0, column=0, columnspan=4, sticky='w', pady=(0, 8))

        self.slot = tk.StringVar()
        self.diameter = tk.StringVar(value='12.36')
        self.rate = tk.StringVar(value='15')
        self.units = tk.StringVar(value='ul/min')
        self.volume = tk.StringVar(value='1.0')
        self.direction = tk.StringVar(value='infuse')

        f = self.frame
        ttk.Label(f, text='Pump').grid(row=1, column=0, sticky='e', padx=4, pady=4)
        self.slot_cb = ttk.Combobox(f, textvariable=self.slot, width=8,
                                    state='readonly')
        self.slot_cb.grid(row=1, column=1, sticky='w')

        self._entry(2, 'Diameter (mm)', self.diameter)
        self._entry(3, 'Rate', self.rate)
        ttk.Label(f, text='Units').grid(row=4, column=0, sticky='e', padx=4, pady=4)
        ttk.Combobox(f, textvariable=self.units, values=UNITS, width=8,
                     state='readonly').grid(row=4, column=1, sticky='w')
        self._entry(5, 'Volume (mL)', self.volume)

        ttk.Label(f, text='Direction').grid(row=6, column=0, sticky='e', padx=4)
        ttk.Radiobutton(f, text='Infuse', value='infuse',
                        variable=self.direction).grid(row=6, column=1, sticky='w')
        ttk.Radiobutton(f, text='Withdraw', value='withdraw',
                        variable=self.direction).grid(row=6, column=2, sticky='w')

        self.run_btn = ttk.Button(f, text='Run', command=self._run)
        self.run_btn.grid(row=7, column=1, sticky='w', pady=8)

        state.on_refresh(self.refresh)
        self.refresh()

    def _entry(self, r, label, var):
        ttk.Label(self.frame, text=label).grid(row=r, column=0, sticky='e',
                                               padx=4, pady=4)
        ttk.Entry(self.frame, textvariable=var, width=10).grid(
            row=r, column=1, sticky='w')

    def refresh(self):
        slots = self.state.registered_slots()
        self.slot_cb.configure(values=slots)
        if self.slot.get() not in slots:
            self.slot.set(slots[0] if slots else '')

    def set_busy(self, busy):
        self.run_btn.configure(state='disabled' if busy else 'normal')

    def _run(self):
        slot = self.slot.get()
        if not slot:
            self.worker.log('No pump selected.', 'error')
            return
        try:
            rate = float(self.rate.get())
            volume = float(self.volume.get())
            diameter = float(self.diameter.get())
        except ValueError:
            self.worker.log('Rate, volume and diameter must be numbers.', 'error')
            return

        pump_id = self.state.pump_id(slot)
        units = self.units.get()
        direction = self.direction.get()
        ctrl = self.state.ctrl

        self.worker.log(
            f'Pump {slot}: {direction} {rate} {units}, {volume} mL, '
            f'dia {diameter} mm')

        def task():
            if direction == 'withdraw':
                ctrl.withdraw(pump_id, rate, units, volume, diameter)
            else:
                ctrl.infuse(pump_id, rate, units, volume, diameter)

        self.worker.run_async(task)
