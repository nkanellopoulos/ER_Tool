import os
import sys
import tempfile
from datetime import datetime
from typing import List
from typing import Set
from urllib.parse import urlparse

from PySide6.QtCore import QProcess
from PySide6.QtCore import QRectF
from PySide6.QtCore import QSettings
from PySide6.QtCore import QSize
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtGui import QIcon
from PySide6.QtGui import QPainter
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
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

        # Add connection string widget
        conn_layout = QHBoxLayout()
        conn_layout.addWidget(QLabel("Connection String:"))
        self.conn_edit = QLineEdit()
        self.conn_edit.setText(os.getenv("DB_CONNECTION", ""))
        self.conn_edit.textChanged.connect(self.on_connection_changed)
        conn_layout.addWidget(self.conn_edit)
        layout.addLayout(conn_layout)

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

        # Create toolbar with sections
        self.toolbar = self.addToolBar("Tools")
        self.toolbar.addSeparator()

        # Set toolbar icon size
        self.toolbar.setIconSize(QSize(24, 24))

        # View actions
        self.toolbar.addWidget(QLabel("View: "))
        zoom_in_action = QAction(
            QIcon.fromTheme("zoom-in", QIcon.fromTheme("view-zoom-in")), "Zoom In", self
        )
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.diagram_view.scale(1.2, 1.2))
        self.toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction(
            QIcon.fromTheme("zoom-out", QIcon.fromTheme("view-zoom-out")),
            "Zoom Out",
            self,
        )
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.diagram_view.scale(0.8, 0.8))
        self.toolbar.addAction(zoom_out_action)

        fit_action = QAction(
            QIcon.fromTheme("zoom-fit-best", QIcon.fromTheme("view-fullscreen")),
            "Fit View",
            self,
        )
        fit_action.setShortcut("Ctrl+0")
        fit_action.triggered.connect(self.fit_view)
        self.toolbar.addAction(fit_action)

        self.toolbar.addSeparator()

        # Selection actions
        self.toolbar.addWidget(QLabel("Selection: "))
        select_all_action = QAction(
            QIcon.fromTheme("edit-select-all"), "Select All", self
        )
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.select_all_tables)
        self.toolbar.addAction(select_all_action)

        deselect_all_action = QAction(
            QIcon.fromTheme("edit-clear", QIcon.fromTheme("edit-delete")),
            "Deselect All",
            self,
        )
        deselect_all_action.setShortcut("Ctrl+D")
        deselect_all_action.triggered.connect(self.deselect_all_tables)
        self.toolbar.addAction(deselect_all_action)

        self.toolbar.addSeparator()

        # Diagram actions
        self.toolbar.addWidget(QLabel("Diagram: "))
        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_diagram)
        self.toolbar.addAction(refresh_action)

        export_action = QAction(
            QIcon.fromTheme("document-save", QIcon.fromTheme("filesave")),
            "Export",
            self,
        )
        export_action.setShortcut("Ctrl+S")
        export_action.triggered.connect(self.export_diagram)
        self.toolbar.addAction(export_action)

        self.show_referenced_action = QAction(
            QIcon.fromTheme("view-list-tree"), "Show Referenced Tables", self
        )
        self.show_referenced_action.setCheckable(True)
        self.show_referenced_action.setChecked(False)
        self.show_referenced_action.triggered.connect(self.refresh_diagram)
        self.toolbar.addAction(self.show_referenced_action)

        self.db_name = "unknown"

        # Load initial data if connection string exists
        if self.conn_edit.text():
            self.load_tables()

        # Disconnect auto-refresh during bulk operations
        self.auto_refresh = True
        self.table_tree.itemChanged.connect(self.on_table_selection_changed)

    def on_connection_changed(self):
        """Handle connection string changes"""
        if self.conn_edit.text():
            self.load_tables()

    def on_table_selection_changed(self, item, column):
        """Handle individual table selection changes"""
        if self.auto_refresh:
            self.refresh_diagram()

    def select_all_tables(self):
        """Select all tables in the tree"""
        self.auto_refresh = False  # Disable auto-refresh
        iterator = QTreeWidgetItemIterator(self.table_tree)
        while iterator.value():
            iterator.value().setCheckState(0, Qt.Checked)
            iterator += 1
        self.auto_refresh = True  # Re-enable auto-refresh
        self.refresh_diagram()

    def deselect_all_tables(self):
        """Deselect all tables in the tree"""
        self.auto_refresh = False  # Disable auto-refresh
        iterator = QTreeWidgetItemIterator(self.table_tree)
        while iterator.value():
            iterator.value().setCheckState(0, Qt.Unchecked)
            iterator += 1
        self.auto_refresh = True  # Re-enable auto-refresh
        self.refresh_diagram()

    def fit_view(self):
        """Fit diagram to view"""
        if self.diagram_view.scene():
            self.diagram_view.fitInView(
                self.diagram_view.scene().itemsBoundingRect(), Qt.KeepAspectRatio
            )

    def load_tables(self):
        """Load tables from database and populate tree widget"""
        try:
            conn_string = self.conn_edit.text()
            if not conn_string:
                raise ValueError("No database connection string provided")

            # Extract database name from connection string
            parsed = urlparse(conn_string)
            self.db_name = parsed.path.strip("/")

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
            generator = DotGenerator(self.tables, self.db_name)
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
            # Generate default filename
            default_name = f"{self.db_name}_{datetime.now().strftime('%Y-%m-%d')}"
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Export Diagram",
                default_name,
                "SVG files (*.svg);;PNG files (*.png);;PDF files (*.pdf)",
            )

            if file_name:
                # Generate DOT file
                generator = DotGenerator(self.tables, self.db_name)
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
