"""Reusable per-slot pump config widget: checkbox + diameter/rate/units/volume/direction.

Used by the Multiple tab (one row per slot) and by each Orchestrate step.
build_config() returns the dict shape run_parallel expects, or None if unchecked.
"""

import tkinter as tk
from tkinter import ttk

from state import SLOTS

UNITS = ['ul/min', 'ul/hr']


class PumpConfigRow:
    DEFAULTS = dict(diameter='12.36', rate='15', units='ul/min',
                    volume='1.0', direction='infuse')

    def __init__(self, parent, slot, state):
        self.slot = slot
        self.state = state
        self.frame = ttk.Frame(parent)

        self.enabled = tk.BooleanVar(value=False)
        self.diameter = tk.StringVar(value=self.DEFAULTS['diameter'])
        self.rate = tk.StringVar(value=self.DEFAULTS['rate'])
        self.units = tk.StringVar(value=self.DEFAULTS['units'])
        self.volume = tk.StringVar(value=self.DEFAULTS['volume'])
        self.direction = tk.StringVar(value=self.DEFAULTS['direction'])

        self._widgets = []

        self.check = ttk.Checkbutton(
            self.frame, text=f'Pump {slot}', variable=self.enabled,
            command=self._sync_enabled)
        self.check.grid(row=0, column=0, padx=4, sticky='w')

        self._labeled(1, 'Dia (mm)', self.diameter, width=7)
        self._labeled(3, 'Rate', self.rate, width=7)
        self._combo(5, 'Units', self.units, UNITS, width=8)
        self._labeled(7, 'Vol (mL)', self.volume, width=7)

        ttk.Label(self.frame, text='Dir').grid(row=0, column=9, padx=(8, 2))
        inf = ttk.Radiobutton(self.frame, text='Infuse', value='infuse',
                              variable=self.direction)
        wd = ttk.Radiobutton(self.frame, text='Withdraw', value='withdraw',
                             variable=self.direction)
        inf.grid(row=0, column=10)
        wd.grid(row=0, column=11)
        self._widgets += [inf, wd]

        self._sync_enabled()

    def _labeled(self, col, label, var, width):
        ttk.Label(self.frame, text=label).grid(row=0, column=col, padx=(8, 2))
        e = ttk.Entry(self.frame, textvariable=var, width=width)
        e.grid(row=0, column=col + 1)
        self._widgets.append(e)

    def _combo(self, col, label, var, values, width):
        ttk.Label(self.frame, text=label).grid(row=0, column=col, padx=(8, 2))
        c = ttk.Combobox(self.frame, textvariable=var, values=values,
                        width=width, state='readonly')
        c.grid(row=0, column=col + 1)
        self._widgets.append(c)

    def _sync_enabled(self):
        registered = self.state.is_registered(self.slot)
        # disable the whole row if the slot is not connected
        self.check.configure(state='normal' if registered else 'disabled')
        if not registered:
            self.enabled.set(False)
        on = registered and self.enabled.get()
        for w in self._widgets:
            state = 'normal'
            if isinstance(w, ttk.Combobox):
                state = 'readonly'
            w.configure(state=state if on else 'disabled')

    def refresh(self):
        self._sync_enabled()

    def grid(self, **kw):
        self.frame.grid(**kw)

    def build_config(self):
        """Return a run_parallel config dict, or None if this row is off."""
        if not (self.state.is_registered(self.slot) and self.enabled.get()):
            return None
        return {
            'pump_id': self.state.pump_id(self.slot),
            'rate': float(self.rate.get()),
            'units': self.units.get(),
            'volume': float(self.volume.get()),
            'diameter_mm': float(self.diameter.get()),
            'direction': self.direction.get(),
        }
