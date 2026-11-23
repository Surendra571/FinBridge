"""
Pytest configuration and helpers for FinBridge backend test suite.
"""
from typing import Any, Coroutine


def run_coroutine(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Drives an async coroutine synchronously to completion.
    Avoids opening Windows network loopback sockets (127.0.0.1) in sandboxed environments.
    """
    try:
        while True:
            coro.send(None)
    except StopIteration as exc:
        return exc.value
