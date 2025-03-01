import os
import sys
import tempfile
from typing import List
from typing import Set

from PySide6.QtCore import QProcess
from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtGui import QPainter
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QSplitter
from PySide6.QtWidgets import QTreeWidget
from PySide6.QtWidgets import QTreeWidgetItem
from PySide6.QtWidgets import QTreeWidgetItemIterator
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from dot_generator import DotGenerator
from schema_reader import SchemaReader


class ERDiagramView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene())
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

    def wheelEvent(self, event):
        """Handle zoom with mouse wheel"""
        factor = 1.1
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        self.scale(factor, factor)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ER Diagram Viewer")
        self.resize(1200, 800)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create splitter for tree and diagram
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Create table tree
        self.table_tree = QTreeWidget()
        self.table_tree.setHeaderLabel("Tables")
        splitter.addWidget(self.table_tree)

        # Create diagram view
        self.diagram_view = ERDiagramView()
        splitter.addWidget(self.diagram_view)

        # Set splitter sizes
        splitter.setSizes([300, 900])

        # Create toolbar
        toolbar = self.addToolBar("Tools")

        # Add refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_diagram)
        toolbar.addAction(refresh_action)

        # Add export action
        export_action = QAction("Export", self)
        export_action.triggered.connect(self.export_diagram)
        toolbar.addAction(export_action)

        # Add show referenced checkbox
        self.show_referenced_action = QAction("Show Referenced Tables", self)
        self.show_referenced_action.setCheckable(True)
        self.show_referenced_action.setChecked(False)
        self.show_referenced_action.triggered.connect(self.refresh_diagram)
        toolbar.addAction(self.show_referenced_action)

        # Load initial data
        self.load_tables()

        # Connect signals
        self.table_tree.itemChanged.connect(self.refresh_diagram)

    def load_tables(self):
        """Load tables from database and populate tree widget"""
        try:
            conn_string = os.getenv("DB_CONNECTION")
            if not conn_string:
                raise ValueError("No database connection string provided")

            self.tables = SchemaReader.from_database(conn_string)

            # Populate tree widget
            self.table_tree.clear()
            for table_name in sorted(self.tables.keys()):
                item = QTreeWidgetItem(self.table_tree)
                item.setText(0, table_name)
                item.setCheckState(0, Qt.Unchecked)

        except Exception as e:
            print(f"Error loading tables: {e}", file=sys.stderr)

    def get_excluded_tables(self) -> List[str]:
        """Get list of unchecked tables"""
        excluded = []
        iterator = QTreeWidgetItemIterator(self.table_tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.Unchecked:
                excluded.append(item.text(0))
            iterator += 1
        return excluded

    def refresh_diagram(self):
        """Generate and display the diagram"""
        try:
            # Generate DOT file
            generator = DotGenerator(self.tables)
            dot_content = generator.generate(
                exclude_tables=self.get_excluded_tables(),
                show_referenced=self.show_referenced_action.isChecked(),
            )

            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as dot_file:
                dot_file.write(dot_content.encode())
                dot_path = dot_file.name

            svg_path = dot_path + ".svg"

            # Run dot to generate SVG
            process = QProcess()
            process.start("dot", ["-Tsvg", dot_path, "-o", svg_path])
            process.waitForFinished()

            # Load SVG into view
            self.diagram_view.scene().clear()
            svg_item = QGraphicsSvgItem(svg_path)
            self.diagram_view.scene().addItem(svg_item)
            self.diagram_view.setSceneRect(QRectF(svg_item.boundingRect()))
            self.diagram_view.fitInView(svg_item, Qt.KeepAspectRatio)

            # Cleanup temporary files
            os.unlink(dot_path)
            os.unlink(svg_path)

        except Exception as e:
            print(f"Error refreshing diagram: {e}", file=sys.stderr)

    def export_diagram(self):
        """Export current diagram to file"""
        try:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Export Diagram",
                "",
                "SVG files (*.svg);;PNG files (*.png);;PDF files (*.pdf)",
            )

            if file_name:
                # Generate DOT file
                generator = DotGenerator(self.tables)
                dot_content = generator.generate(
                    exclude_tables=self.get_excluded_tables()
                )

                # Create temporary dot file
                with tempfile.NamedTemporaryFile(
                    suffix=".dot", delete=False
                ) as dot_file:
                    dot_file.write(dot_content.encode())
                    dot_path = dot_file.name

                # Determine output format
                output_format = os.path.splitext(file_name)[1][1:]

                # Run dot to generate output file
                process = QProcess()
                process.start("dot", [f"-T{output_format}", dot_path, "-o", file_name])
                process.waitForFinished()

                # Cleanup
                os.unlink(dot_path)

        except Exception as e:
            print(f"Error exporting diagram: {e}", file=sys.stderr)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
