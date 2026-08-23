"""Cooperative stop flag for the job scan pipeline."""
from __future__ import annotations

import threading

_stop = threading.Event()


def request_stop() -> None:
    _stop.set()


def clear_stop() -> None:
    _stop.clear()


def should_stop() -> bool:
    return _stop.is_set()
