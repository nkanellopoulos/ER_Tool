from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtWidgets import QGraphicsView


class ERDiagramView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene())
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.zoom_level = 1.0

    def wheelEvent(self, event):
        """Handle mouse wheel for panning and zooming"""
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.1 if event.angleDelta().y() > 0 else 1.0 / 1.1
            self.scale(factor, factor)
        else:
            if event.modifiers() & Qt.ShiftModifier:
                delta = event.angleDelta().y()
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() - delta
                )
            else:
                delta = event.angleDelta().y()
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() - delta
                )

    def scale(self, sx: float, sy: float):
        """Override scale to track zoom level"""
        super().scale(sx, sy)
        self.zoom_level *= sx
        if hasattr(self, "on_zoom_changed"):
            self.on_zoom_changed(self.zoom_level)

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
