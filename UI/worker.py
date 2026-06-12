"""Keeps tkinter responsive: blocking controller calls run on a thread,
results come back to the GUI through a queue drained by root.after()."""

import queue
import threading


class Worker:
    def __init__(self):
        self.events = queue.Queue()
        self._busy = False

    def is_busy(self):
        return self._busy

    def log(self, text, level='info'):
        """Push a log line. Safe to call from any thread."""
        self.events.put(('log', level, text))

    def run_async(self, fn, on_done=None):
        """Run blocking fn() on a worker thread. Pushes log/done/error events."""
        if self._busy:
            self.log('Busy — wait for the current run to finish.', 'error')
            return

        self._busy = True
        self.events.put(('busy', True, None))

        def _target():
            try:
                fn()
                self.events.put(('log', 'info', 'Done.'))
            except Exception as e:
                self.events.put(('log', 'error', f'{type(e).__name__}: {e}'))
            finally:
                self._busy = False
                self.events.put(('busy', False, None))
                if on_done:
                    self.events.put(('callback', None, on_done))

        threading.Thread(target=_target, daemon=True).start()

    def drain(self, log_widget, on_busy_change):
        """Called from the GUI thread via root.after. Applies queued events."""
        while True:
            try:
                kind, a, b = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                _append_log(log_widget, b, level=a)
            elif kind == 'busy':
                on_busy_change(a)
            elif kind == 'callback':
                try:
                    b()
                except Exception:
                    pass


def _append_log(widget, text, level='info'):
    widget.configure(state='normal')
    tag = 'err' if level == 'error' else 'msg'
    widget.insert('end', text + '\n', tag)
    widget.see('end')
    widget.configure(state='disabled')
