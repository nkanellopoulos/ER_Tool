"""
Debugging utilities for the ER Tool.
"""

import inspect
import os
import sys
import time
import traceback
from functools import wraps


def trace_calls(func):
    """
    Decorator to trace function calls with call stack information.

    This helps identify which code path is triggering a function call.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        frame = inspect.currentframe().f_back
        caller_info = inspect.getframeinfo(frame)
        caller = f"{os.path.basename(caller_info.filename)}:{caller_info.lineno}"

        # Print call information
        print(f"\nCALL TRACE: {func.__qualname__} called from {caller}")

        # Get partial call stack (exclude this frame)
        stack = traceback.extract_stack()[:-1]
        print(f"Call stack ({len(stack)} frames):")
        for i, (filename, lineno, name, line) in enumerate(stack[-5:], 1):
            if "python" not in filename.lower():  # Skip standard library frames
                print(f"  {i}. {os.path.basename(filename)}:{lineno} - {name}()")

        # Call the original function
        return func(*args, **kwargs)

    return wrapper


class DebugTimer:
    """
    Simple context manager for timing code execution.

    Usage:
        with DebugTimer("Operation name"):
            # code to time
    """

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start
        print(f"{self.name} took {duration:.4f} seconds")


def monitor_method(cls, method_name):
    """
    Monkey patch a method to monitor when it's being called.

    Usage:
        monitor_method(MainWindow, "refresh_diagram")
    """
    original = getattr(cls, method_name)

    @wraps(original)
    def monitored(*args, **kwargs):
        print(f"\nMethod {cls.__name__}.{method_name} called")
        traceback.print_stack(limit=8)
        return original(*args, **kwargs)

    setattr(cls, method_name, monitored)
    print(f"Monitoring {cls.__name__}.{method_name}")


def inspect_qt_connections(widget):
    """
    Attempt to dump signal-slot connections for a Qt widget.
    """
    # Note: This relies on QtCore internals and may not always work
    try:
        connections = widget.findChildren(widget.metaObject().className())
        print(f"Connections for {widget.__class__.__name__}:")
        for conn in connections:
            print(f"  {conn.objectName()}")
    except Exception as e:
        print(f"Could not inspect connections: {e}")
