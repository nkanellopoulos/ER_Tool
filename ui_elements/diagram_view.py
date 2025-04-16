from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtGui import QColor
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtWidgets import QGraphicsView


class DarkModeGraphicsScene(QGraphicsScene):
    """A custom scene that supports dark mode"""

    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.setBackgroundBrush(QBrush(QColor(255, 255, 255)))  # Default white

    def set_dark_mode(self, enabled: bool):
        """Set dark mode state - using 50% gray for dark mode"""
        if self.dark_mode == enabled:
            # Don't do anything if dark mode hasn't changed
            return

        self.dark_mode = enabled
        if enabled:
            # Use gray for dark mode to match DOT background
            self.setBackgroundBrush(QBrush(QColor(180, 180, 180)))
        else:
            # White background for light mode
            self.setBackgroundBrush(QBrush(QColor(250, 250, 250)))

        # Force update the entire scene
        self.update()


class ERDiagramView(QGraphicsView):
    def __init__(self):
        super().__init__()
        # Create a custom scene that supports dark mode
        self.setScene(DarkModeGraphicsScene())
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.zoom_level = 1.0

        # Dark mode property
        self.dark_canvas = False

    def wheelEvent(self, event):
        """Handle mouse wheel for panning and zooming"""
        if event.modifiers() & Qt.ControlModifier:
            # Calculate zoom based on delta for smoother increments
            delta = event.angleDelta().y()
            factor = pow(1.05, delta / 120.0)  # Smooth exponential zoom

            new_zoom = self.zoom_level * factor
            if 0.08 <= new_zoom <= 3.0:
                self.scale(factor, factor)
                self.zoom_level = new_zoom
                if hasattr(self, "on_zoom_changed"):
                    self.on_zoom_changed(self.zoom_level)
            event.accept()
        else:
            # Make scrolling smoother too
            if event.modifiers() & Qt.ShiftModifier:
                delta = event.angleDelta().y() / 2
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta
                )
            else:
                delta = event.angleDelta().y() / 2
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta
                )

    def scale(self, sx: float, sy: float):
        """Override scale to track zoom level properly"""
        # Only apply the scale if it would keep us within reasonable bounds
        new_zoom = self.zoom_level * sx
        if 0.05 <= new_zoom <= 5.0:
            super().scale(sx, sy)
            self.zoom_level = new_zoom
            if hasattr(self, "on_zoom_changed") and self.on_zoom_changed:
                self.on_zoom_changed(self.zoom_level)
        else:
            print(
                f"Ignoring scale operation - would result in zoom level {new_zoom:.2f}"
            )

    def resetTransform(self):
        """Override resetTransform to reset zoom level"""
        super().resetTransform()
        self.zoom_level = 1.0
        if hasattr(self, "on_zoom_changed"):
            self.on_zoom_changed(self.zoom_level)

    def fitInView(
        self, rect: QRectF, aspect_ratio_mode: Qt.AspectRatioMode = Qt.IgnoreAspectRatio
    ):
        """Override fitInView to track zoom level"""
        super().fitInView(rect, aspect_ratio_mode)
        transform = self.transform()
        self.zoom_level = transform.m11()
        if hasattr(self, "on_zoom_changed"):
            self.on_zoom_changed(self.zoom_level)

    def set_dark_canvas(self, enabled: bool):
        """Enable or disable dark canvas mode"""
        self.dark_canvas = enabled
        # Update the scene background
        if isinstance(self.scene(), DarkModeGraphicsScene):
            self.scene().set_dark_mode(enabled)
            # Force a repaint
            self.viewport().update()
