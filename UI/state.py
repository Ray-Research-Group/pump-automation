"""Shared app state: the controller, slot->pump mapping, and refresh callbacks."""

SLOTS = ['A', 'B', 'C']
SLOT_PUMP_ID = {'A': 'pump_a', 'B': 'pump_b', 'C': 'pump_c'}


class AppState:
    def __init__(self, controller):
        self.ctrl = controller
        # slot -> description string while registered, else None
        self.registered = {s: None for s in SLOTS}
        self._refresh_callbacks = []

    def pump_id(self, slot):
        return SLOT_PUMP_ID[slot]

    def is_registered(self, slot):
        return self.registered[slot] is not None

    def registered_slots(self):
        return [s for s in SLOTS if self.is_registered(s)]

    def mark_registered(self, slot, description):
        self.registered[slot] = description
        self.fire_refresh()

    def mark_unregistered(self, slot):
        self.registered[slot] = None
        self.fire_refresh()

    def on_refresh(self, callback):
        """Register a callback fired whenever registration changes."""
        self._refresh_callbacks.append(callback)

    def fire_refresh(self):
        for cb in self._refresh_callbacks:
            cb()
