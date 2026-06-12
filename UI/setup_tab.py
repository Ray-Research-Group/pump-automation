"""Setup tab: map each slot A/B/C to a Harvard or New Era pump on a COM port."""

import tkinter as tk
from tkinter import ttk

from serial.tools import list_ports

from state import SLOTS

TYPES = ['— none —', 'Harvard', 'New Era']

# Suggested defaults from the hardware table in Claude.md
DEFAULTS = {
    'A': ('Harvard', 'COM6', '0'),
    'B': ('New Era', 'COM7', '0'),
    'C': ('New Era', 'COM7', '1'),
}


class SetupTab:
    def __init__(self, notebook, state, worker):
        self.state = state
        self.worker = worker
        self.frame = ttk.Frame(notebook, padding=12)
        self.rows = {}

        ttk.Label(self.frame, text='Pump Setup',
                  font=('TkDefaultFont', 13, 'bold')).grid(
            row=0, column=0, columnspan=8, sticky='w', pady=(0, 8))

        ttk.Button(self.frame, text='Refresh ports',
                   command=self.refresh_ports).grid(row=0, column=7, sticky='e')

        for i, slot in enumerate(SLOTS):
            self._build_row(i + 1, slot)

        self.refresh_ports()

    def _build_row(self, r, slot):
        f = self.frame
        ttk.Label(f, text=f'Pump {slot}',
                  font=('TkDefaultFont', 11, 'bold')).grid(
            row=r, column=0, padx=4, pady=6, sticky='w')

        dtype, dport, daddr = DEFAULTS[slot]
        type_var = tk.StringVar(value=dtype)
        port_var = tk.StringVar(value=dport)
        addr_var = tk.StringVar(value=daddr)
        status_var = tk.StringVar(value='not connected')

        ttk.Label(f, text='Type').grid(row=r, column=1, padx=(8, 2))
        type_cb = ttk.Combobox(f, textvariable=type_var, values=TYPES,
                               width=10, state='readonly')
        type_cb.grid(row=r, column=2)

        ttk.Label(f, text='Port').grid(row=r, column=3, padx=(8, 2))
        port_cb = ttk.Combobox(f, textvariable=port_var, width=12)
        port_cb.grid(row=r, column=4)

        ttk.Label(f, text='Addr').grid(row=r, column=5, padx=(8, 2))
        addr_cb = ttk.Combobox(f, textvariable=addr_var,
                               values=[str(i) for i in range(10)],
                               width=4, state='readonly')
        addr_cb.grid(row=r, column=6)

        connect_btn = ttk.Button(f, text='Connect',
                                 command=lambda: self._connect(slot))
        connect_btn.grid(row=r, column=7, padx=(8, 2))
        disconnect_btn = ttk.Button(f, text='Disconnect',
                                    command=lambda: self._disconnect(slot))
        disconnect_btn.grid(row=r, column=8, padx=2)

        status_lbl = ttk.Label(f, textvariable=status_var, foreground='gray')
        status_lbl.grid(row=r, column=9, padx=8, sticky='w')

        self.rows[slot] = dict(
            type=type_var, port=port_var, addr=addr_var, status=status_var,
            type_cb=type_cb, addr_cb=addr_cb,
            connect=connect_btn, disconnect=disconnect_btn,
            status_lbl=status_lbl)

        def sync_addr(*_):
            addr_cb.configure(
                state='readonly' if type_var.get() == 'New Era' else 'disabled')
        type_var.trace_add('write', sync_addr)
        sync_addr()
        self._set_row_state(slot, connected=False)

    def refresh_ports(self):
        ports = [p.device for p in list_ports.comports()]
        for slot, row in self.rows.items():
            current = row['port'].get()
            values = sorted(set(ports + ([current] if current else [])))
            cb = self.frame.grid_slaves(row=SLOTS.index(slot) + 1, column=4)
            if cb:
                cb[0].configure(values=values)

    def _set_row_state(self, slot, connected):
        row = self.rows[slot]
        row['connect'].configure(state='disabled' if connected else 'normal')
        row['disconnect'].configure(state='normal' if connected else 'disabled')
        for key in ('type_cb', 'addr_cb'):
            row[key].configure(state='disabled' if connected else 'readonly')
        port_cb = self.frame.grid_slaves(row=SLOTS.index(slot) + 1, column=4)
        if port_cb:
            port_cb[0].configure(state='disabled' if connected else 'normal')

    def _connect(self, slot):
        row = self.rows[slot]
        ptype = row['type'].get()
        port = row['port'].get().strip()
        pump_id = self.state.pump_id(slot)

        if ptype == '— none —':
            self.worker.log(f'Pump {slot}: pick a type first.', 'error')
            return
        if not port:
            self.worker.log(f'Pump {slot}: pick a COM port first.', 'error')
            return

        try:
            if ptype == 'Harvard':
                self.state.ctrl.add_harvard(pump_id, port=port)
                desc = f'Harvard on {port}'
            else:
                addr = int(row['addr'].get())
                self.state.ctrl.add_new_era(pump_id, port=port, address=addr)
                desc = f'New Era on {port} addr {addr}'
        except Exception as e:
            self.worker.log(f'Pump {slot} connect failed: {e}', 'error')
            return

        self.state.mark_registered(slot, desc)
        row['status'].set(desc)
        row['status_lbl'].configure(foreground='green')
        self._set_row_state(slot, connected=True)
        self.worker.log(f'Pump {slot} → {desc}')

    def _disconnect(self, slot):
        pump_id = self.state.pump_id(slot)
        try:
            pump = self.state.ctrl.get(pump_id)
            pump.close()
        except Exception as e:
            self.worker.log(f'Pump {slot} disconnect: {e}', 'error')
        # drop our mapping regardless
        self.state.ctrl._pumps.pop(pump_id, None)
        self.state.mark_unregistered(slot)
        self.rows[slot]['status'].set('not connected')
        self.rows[slot]['status_lbl'].configure(foreground='gray')
        self._set_row_state(slot, connected=False)
        self.worker.log(f'Pump {slot} disconnected.')
