"""Lightweight timing utilities for performance debugging."""
import time
from contextlib import contextmanager
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


def now_ms() -> float:
    """Return current time in milliseconds using high-resolution timer."""
    return time.perf_counter() * 1000


@contextmanager
def time_operation(label: str, log_fn: Optional[Callable[[str], None]] = None, min_ms: float = 0.0):
    """
    Context manager to time an operation and log elapsed time.
    
    Args:
        label: Description of the operation being timed
        log_fn: Optional logging function (defaults to logger.debug)
        min_ms: Only log if elapsed time >= min_ms (default: 0, always log)
    
    Example:
        with time_operation("fetch_books"):
            books = db.query(Book).all()
    """
    start = now_ms()
    try:
        yield
    finally:
        elapsed = now_ms() - start
        if elapsed >= min_ms:
            if log_fn:
                log_fn(f"{label}: {elapsed:.2f}ms")
            else:
                logger.debug(f"{label}: {elapsed:.2f}ms")


def log_elapsed(start_ms: float, label: str, log_fn: Optional[Callable[[str], None]] = None) -> float:
    """
    Log elapsed time since start_ms and return current time.
    
    Args:
        start_ms: Start time in milliseconds (from now_ms())
        label: Description of the operation
        log_fn: Optional logging function (defaults to logger.debug)
    
    Returns:
        Current time in milliseconds (for chaining)
    
    Example:
        t = now_ms()
        t = log_elapsed(t, "step1")
        t = log_elapsed(t, "step2")
    """
    elapsed = now_ms() - start_ms
    if log_fn:
        log_fn(f"{label}: {elapsed:.2f}ms")
    else:
        logger.debug(f"{label}: {elapsed:.2f}ms")
    return now_ms()

