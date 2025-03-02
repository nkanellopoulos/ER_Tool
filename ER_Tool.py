import atexit
import os
import os.path
import sys
import tempfile
from datetime import datetime
from typing import List
from urllib.parse import urlparse

from PySide6.QtCore import QProcess
from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QSplitter
from PySide6.QtWidgets import QTreeWidget
from PySide6.QtWidgets import QTreeWidgetItem
from PySide6.QtWidgets import QTreeWidgetItemIterator
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from dot_generator import DotGenerator
from schema_reader import SchemaReader
from ui_elements import ConnectionDialog
from ui_elements import ERDiagramView
from ui_elements import StatusBarManager
from ui_elements import ToolbarManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Store temporary files for cleanup on exit
        self.temp_files = []
        atexit.register(self.cleanup_temp_files)

        self.setWindowTitle("ER Diagram Tool")
        self.resize(1500, 900)

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create splitter for tree and diagram
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Create table tree and diagram view
        self.table_tree = QTreeWidget()
        self.table_tree.setHeaderLabel("Tables")
        self.diagram_view = ERDiagramView()

        # Add widgets to splitter in order
        splitter.addWidget(self.table_tree)
        splitter.addWidget(self.diagram_view)

        # Create managers and menus
        menubar = self.menuBar()
        self.status_bar_manager = StatusBarManager(self)
        self.toolbar_manager = ToolbarManager(self)
        self._setup_menus(menubar)

        # Initialize prefix from environment and set up handler
        self.status_bar_manager.set_prefix(os.getenv("TABLE_PREFIX", ""))
        self.status_bar_manager.set_prefix_handler(self.refresh_diagram)

        # Connect signals
        self.diagram_view.on_zoom_changed = self.status_bar_manager.update_zoom
        self.show_referenced_action = self.toolbar_manager.show_referenced_action

        # Set splitter sizes with exact 1:3 ratio AFTER all widgets are added
        total_width = self.width()
        splitter.setSizes([total_width // 4, (total_width * 3) // 4])

        # Initialize connection from environment
        if os.getenv("ER_DB_CONNECTION"):
            self.connection_string = os.getenv("ER_DB_CONNECTION")
            self.load_tables()
        else:
            self.connection_string = ""
            self.update_status_bar()

        # Create connection action
        connect_action = QAction("Connect to Database", self)
        connect_action.setShortcut("Ctrl+B")  # B for database
        connect_action.triggered.connect(self.show_connection_dialog)

        # Add to menu and toolbar
        database_menu = menubar.addMenu("&Database")
        database_menu.addAction(connect_action)

        # Disconnect auto-refresh during bulk operations
        self.auto_refresh = True
        self.table_tree.itemChanged.connect(self.on_table_selection_changed)

        # Hook up zoom tracking
        self.diagram_view.on_zoom_changed = self._update_zoom_label

    def _setup_menus(self, menubar):
        """Setup application menus"""
        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.toolbar_manager.zoom_in_action)
        view_menu.addAction(self.toolbar_manager.zoom_out_action)
        view_menu.addAction(self.toolbar_manager.zoom_100_action)
        view_menu.addAction(self.toolbar_manager.fit_action)
        view_menu.addSeparator()
        view_menu.addAction(self.toolbar_manager.show_referenced_action)

        # Selection menu
        selection_menu = menubar.addMenu("&Selection")
        selection_menu.addAction(self.toolbar_manager.select_all_action)
        selection_menu.addAction(self.toolbar_manager.deselect_all_action)

        # Diagram menu
        diagram_menu = menubar.addMenu("&Diagram")
        diagram_menu.addAction(self.toolbar_manager.refresh_action)
        diagram_menu.addAction(self.toolbar_manager.export_action)

        # Database menu
        database_menu = menubar.addMenu("&Database")
        database_menu.addAction(self.toolbar_manager.connect_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def on_connection_changed(self):
        """Handle connection string changes"""
        if self.conn_edit.text():
            self.load_tables()

    def on_table_selection_changed(self, item, column):
        """Handle individual table selection changes"""
        if self.auto_refresh:
            self.refresh_diagram()
            self.update_status_bar()

    def select_all_tables(self):
        """Select all tables in the tree"""
        self.auto_refresh = False  # Disable auto-refresh
        iterator = QTreeWidgetItemIterator(self.table_tree)
        while iterator.value():
            iterator.value().setCheckState(0, Qt.Checked)
            iterator += 1
        self.auto_refresh = True  # Re-enable auto-refresh
        self.refresh_diagram()
        self.update_status_bar()

    def deselect_all_tables(self):
        """Deselect all tables in the tree"""
        self.auto_refresh = False  # Disable auto-refresh
        iterator = QTreeWidgetItemIterator(self.table_tree)
        while iterator.value():
            iterator.value().setCheckState(0, Qt.Unchecked)
            iterator += 1
        self.auto_refresh = True  # Re-enable auto-refresh
        self.refresh_diagram()
        self.update_status_bar()

    def fit_view(self):
        """Fit diagram to view"""
        if self.diagram_view.scene():
            self.diagram_view.fitInView(
                self.diagram_view.scene().itemsBoundingRect(), Qt.KeepAspectRatio
            )

    def _zoom_100(self):
        """Set zoom level to 100%"""
        self.diagram_view.resetTransform()
        self.diagram_view.scale(1.0, 1.0)
        self._update_zoom_label(1.0)

    def _update_zoom_label(self, zoom_level: float):
        """Update zoom level display"""
        self.status_bar_manager.update_zoom(zoom_level)

    def _on_zoom_edit(self):
        """Delegate zoom edit handling to status bar manager"""
        self.status_bar_manager.handle_zoom_edit()

    def load_tables(self):
        """Load tables from database and populate tree widget"""
        try:
            if not hasattr(self, "connection_string") or not self.connection_string:
                raise ValueError("No database connection string provided")

            # Extract database name from connection string
            parsed = urlparse(self.connection_string)
            self.db_name = parsed.path.strip("/")

            self.tables = SchemaReader.from_database(self.connection_string)

            # Populate tree widget
            self.table_tree.clear()
            for table_name in sorted(self.tables.keys()):
                item = QTreeWidgetItem(self.table_tree)
                item.setText(0, table_name)
                item.setCheckState(0, Qt.Unchecked)

            self.update_status_bar()

        except Exception as e:
            print(f"Error loading tables: {e}", file=sys.stderr)
            QMessageBox.warning(self, "Connection Error", str(e))

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
            generator = DotGenerator(
                self.tables,
                self.db_name,
                table_prefix=self.status_bar_manager.get_prefix(),
            )
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

            # Reset transform before fitting to view
            self.diagram_view.resetTransform()
            self.diagram_view.fitInView(svg_item, Qt.KeepAspectRatio)

            # Cleanup temporary files
            os.unlink(dot_path)
            os.unlink(svg_path)

            self.update_status_bar()  # Add status bar update at end of refresh

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

    def cleanup_temp_files(self):
        """Clean up temporary files on application exit"""
        for tmp_file in self.temp_files:
            try:
                if os.path.exists(tmp_file):
                    os.unlink(tmp_file)
            except Exception as e:
                print(
                    f"Error cleaning up temporary file {tmp_file}: {e}", file=sys.stderr
                )

    def show_about_dialog(self):
        """Show the About dialog"""
        QMessageBox.about(
            self,
            "About ER Diagram Tool",
            "ER Diagram Tool\n\n© Nikos Kanellopoulos, 2025",
        )

    def show_connection_dialog(self):
        """Show the database connection dialog"""
        dialog = ConnectionDialog(self)
        if hasattr(self, "connection_string"):
            dialog.set_connection_string(self.connection_string)

        # Connect to dialog's accepted signal
        dialog.accepted.connect(lambda: self._on_connection_accepted(dialog))

        # Show dialog non-modally
        dialog.show()

    def _on_connection_accepted(self, dialog: ConnectionDialog):
        """Handle accepted connection dialog"""
        self.connection_string = dialog.get_connection_string()
        self.load_tables()
        dialog.deleteLater()  # Clean up the dialog

    def update_status_bar(self):
        """Update status bar information"""
        if hasattr(self, "connection_string") and self.connection_string:
            try:
                db_type, rest = self.connection_string.split("://")
                auth, location = rest.split("@")
                user, _ = auth.split(":")
                host_port, db = location.split("/")

                total = len(self.tables) if hasattr(self, "tables") else 0
                selected = total - len(self.get_excluded_tables()) if total > 0 else 0

                self.status_bar_manager.update_connection_info(
                    db_type=db_type,
                    user=user,
                    schema=db,
                    total=total,
                    selected=selected,
                )
            except:
                self.status_bar_manager.update_connection_info()
        else:
            self.status_bar_manager.update_connection_info()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
