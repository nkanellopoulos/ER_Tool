# Now that we've imported all submodules, disallow connections between signals and known refresh methods
from PySide6.QtCore import QObject

from .connection_dialog import ConnectionDialog
from .diagram_view import ERDiagramView
from .status_bar_manager import StatusBarManager
from .toolbar_manager import ToolbarManager

# Store the original connect method
original_connect = QObject.connect


# Define a wrapper to prevent problematic connections
def safe_connect(self, signal, slot):
    # Check if this is connecting to a refresh diagram method
    slot_name = slot.__name__ if hasattr(slot, "__name__") else str(slot)

    # List of sensitive method names that might cause loops
    sensitive_methods = [
        "refresh_diagram",
        "update_status_bar",
        "apply_filter",
        "handle_prefix_edit",
    ]

    if any(method in slot_name for method in sensitive_methods):
        # Only allow certain connections
        caller_name = (
            signal.__self__.__class__.__name__
            if hasattr(signal, "__self__")
            else "Unknown"
        )
        print(f"⚠️ Monitoring signal connection from {caller_name} to {slot_name}")

    # Call the original connect method
    return original_connect(self, signal, slot)


# Replace the connect method with our wrapped version
# QObject.connect = safe_connect  # Uncomment if needed for debugging

__all__ = [
    "ConnectionDialog",
    "ERDiagramView",
    "StatusBarManager",
    "ToolbarManager",
]
