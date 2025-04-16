import atexit
import hashlib
import os
import os.path
import sys
import tempfile
import time
from datetime import datetime
from typing import Dict
from typing import List
from typing import Set
from urllib.parse import urlparse

from PySide6.QtCore import QCoreApplication
from PySide6.QtCore import QEvent
from PySide6.QtCore import QProcess
from PySide6.QtCore import QRectF
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtGui import QColor  # Add this import for QColor
from PySide6.QtGui import QFont
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

from cleanup_temp_files import cleanup_temp_files
from dot_generator import DotGenerator
from schema_reader import SchemaReader
from ui_elements import ConnectionDialog
from ui_elements import ERDiagramView
from ui_elements import StatusBarManager
from ui_elements import ToolbarManager
from ui_elements.diagram_view import DarkModeGraphicsScene  # Add this import


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Store temporary files for cleanup on exit
        self.temp_files = []
        atexit.register(self.cleanup_temp_files)

        # Initialize filter variables
        self.filter_text = ""
        self.matching_tables = set()
        self.matching_fields = {}

        # Add diagram cache
        self._diagram_cache = {}

        # Add a flag to prevent recursive refreshes
        self._refreshing = False

        # Add counter to detect excessive refresh calls
        self._refresh_counter = 0

        # Add a dictionary to track last checkbox states
        self._last_check_state = {}

        # Add show only filtered flag
        self.show_only_filtered = False

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

        # Connect the toolbar filter to our filter handler
        self.toolbar_manager.filter_edit.textChanged.connect(self.on_filter_changed)
        self.toolbar_manager.filter_edit.returnPressed.connect(self.apply_filter)

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

        # Disconnect auto-refresh during bulk operations
        self.auto_refresh = True
        self.table_tree.itemChanged.connect(self.on_table_selection_changed)

        # Hook up zoom tracking
        self.diagram_view.on_zoom_changed = self._update_zoom_label

        # Setup tree view selection handling
        self.setup_tree_view()

    def changeEvent(self, event):
        """Handle palette changes for dark mode"""
        if event.type() == QEvent.Type.PaletteChange:
            # Force toolbar to update icons
            self.toolbar_manager.toolbar.update()
        super().changeEvent(event)

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
        view_menu.addAction(self.toolbar_manager.overview_action)

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
        # Skip during filtering operations or when auto-refresh is disabled
        if not self.auto_refresh or self._refreshing:
            return

        # Only proceed if the change is related to the checkbox state (column 0)
        if column == 0 and item.checkState(0) != self._last_check_state.get(item, None):
            self._last_check_state = getattr(self, "_last_check_state", {})
            self._last_check_state[item] = item.checkState(0)
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

    def _build_cache_key(self):
        """Build a unique key for the current diagram state for caching"""
        # Components that affect the diagram
        components = [
            ",".join(sorted(self.get_excluded_tables())),
            str(self.show_referenced_action.isChecked()),
            str(self.toolbar_manager.overview_action.isChecked()),
            self.status_bar_manager.get_prefix(),
            ",".join(sorted(self.matching_tables)),
            str(self.matching_fields),
            str(self.show_only_filtered),  # Add show_only_filtered to cache key
        ]
        key = "|".join(components)
        return key

    def refresh_diagram(self):
        """Generate and display the diagram"""
        # Skip if no tables loaded yet
        if not hasattr(self, "tables") or not self.tables:
            return

        # Add stack trace for debugging event loop cycles
        if self._refreshing:
            import traceback

            print("Recursive diagram refresh detected from:")
            traceback.print_stack()
            return

        # Count refresh calls and log if excessive
        self._refresh_counter += 1
        if self._refresh_counter > 150:
            print("⛔ Too many refreshes, stopping refresh cycle")
            return

        # Save current zoom level only - we'll center view later
        current_zoom = self.diagram_view.zoom_level
        print(f"Saving current zoom level: {current_zoom:.2f}")

        self._refreshing = True

        try:
            cache_key = self._build_cache_key()

            # Check if we have a cached diagram
            if cache_key in self._diagram_cache:
                # Use cached SVG directly
                svg_path = self._diagram_cache[cache_key]["svg_path"]
                # Verify the file still exists (it might have been cleaned up)
                if os.path.exists(svg_path):
                    # Load SVG into view
                    self.diagram_view.scene().clear()
                    svg_item = QGraphicsSvgItem(svg_path)
                    self.diagram_view.scene().addItem(svg_item)
                    self.diagram_view.setSceneRect(QRectF(svg_item.boundingRect()))
                    self.diagram_view.resetTransform()
                    self.diagram_view.fitInView(svg_item, Qt.KeepAspectRatio)
                    self.update_status_bar()
                    return

            # Start timing
            start_time = time.time()
            total_start = start_time

            # Generate DOT content
            generator = DotGenerator(
                self.tables,
                self.db_name,
                table_prefix=self.status_bar_manager.get_prefix(),
            )
            # Set whether to draw excluded tables note (off by default)
            generator.draw_excluded_tables_note = False

            # Check if dark mode is enabled
            dark_mode_enabled = False
            if hasattr(self.toolbar_manager, "dark_canvas_action"):
                dark_mode_enabled = self.toolbar_manager.dark_canvas_action.isChecked()

            dot_content = generator.generate(
                exclude_tables=self.get_excluded_tables(),
                show_referenced=self.show_referenced_action.isChecked(),
                overview_mode=self.toolbar_manager.overview_action.isChecked(),
                matching_tables=self.matching_tables,
                matching_fields=self.matching_fields,
                show_only_filtered=self.show_only_filtered,
                dark_mode=dark_mode_enabled,  # Pass dark mode setting to generator
            )

            # Log dot generation time
            dot_gen_time = time.time() - start_time
            print(f"DOT generation took {dot_gen_time:.2f} seconds")

            # Create hash for the dot_content to use for caching
            content_hash = hashlib.md5(dot_content.encode()).hexdigest()
            # Reset timer for next step
            start_time = time.time()
            # Create temporary directory for our files
            temp_dir = tempfile.mkdtemp()
            dot_path = os.path.join(temp_dir, f"diagram_{content_hash}.dot")
            svg_path = os.path.join(temp_dir, f"diagram_{content_hash}.svg")
            # Write DOT file
            with open(dot_path, "w") as dot_file:
                dot_file.write(dot_content)

            # Log DOT file writing time
            file_write_time = time.time() - start_time
            print(f"DOT file writing took {file_write_time:.2f} seconds")

            # Reset timer for Graphviz
            start_time = time.time()
            # Run dot to generate SVG
            process = QProcess()
            process.start("dot", ["-Tsvg", dot_path, "-o", svg_path])
            process.waitForFinished(30000)  # 30 second timeout (increased for testing)
            # Check for process errors
            if process.exitCode() != 0:
                error_output = process.readAllStandardError().data().decode()
                print(
                    f"Graphviz error (code {process.exitCode()}): {error_output}",
                    file=sys.stderr,
                )
                raise RuntimeError(f"Graphviz failed: {error_output}")

            # Log Graphviz processing time
            graphviz_time = time.time() - start_time
            print(f"Graphviz processing took {graphviz_time:.2f} seconds")

            # Reset timer for SVG loading
            start_time = time.time()
            # Verify the file exists
            if not os.path.exists(svg_path):
                raise FileNotFoundError(f"SVG file not created: {svg_path}")

            # Get SVG file size for logging
            svg_size = os.path.getsize(svg_path)
            print(f"SVG file size: {svg_size/1024:.2f} KB")

            # Load SVG into view
            self.diagram_view.scene().clear()
            svg_item = QGraphicsSvgItem(svg_path)
            self.diagram_view.scene().addItem(svg_item)
            self.diagram_view.setSceneRect(QRectF(svg_item.boundingRect()))
            # Store in cache
            self._diagram_cache[cache_key] = {
                "dot_path": dot_path,
                "svg_path": svg_path,
                "temp_dir": temp_dir,
            }
            # Limit cache size to 5 entries
            if len(self._diagram_cache) > 5:
                oldest_key = list(self._diagram_cache.keys())[0]
                # Remove oldest cached item
                cache_entry = self._diagram_cache.pop(oldest_key)
                # Add to cleanup list
                self.temp_files.append(cache_entry["temp_dir"])
            # Reset transform before fitting to view
            self.diagram_view.resetTransform()
            self.diagram_view.fitInView(svg_item, Qt.KeepAspectRatio)

            # When adding SVG to the view, make sure to reset the dark mode
            if isinstance(self.diagram_view.scene(), DarkModeGraphicsScene):
                dark_mode_enabled = self.toolbar_manager.dark_canvas_action.isChecked()
                self.diagram_view.scene().set_dark_mode(dark_mode_enabled)

            # Now apply saved zoom level if it exists (but center view)
            if current_zoom > 0.1:  # Minimum threshold
                # Calculate required scaling to get from fit-zoom to saved zoom
                fit_zoom = self.diagram_view.zoom_level
                zoom_factor = current_zoom / fit_zoom

                # Scale to desired zoom level
                self.diagram_view.scale(zoom_factor, zoom_factor)

                print(f"Restored zoom level to {current_zoom:.2f}")

            # Log SVG loading time
            svg_load_time = time.time() - start_time
            print(f"SVG loading took {svg_load_time:.2f} seconds")

            # Add to cleanup list - will be cleaned up on exit
            self.temp_files.append(temp_dir)
            self.update_status_bar()
            # Log total time
            total_time = time.time() - total_start
            print(f"Total diagram refresh took {total_time:.2f} seconds")
            print(
                f"Breakdown: DOT gen={dot_gen_time:.2f}s, Graphviz={graphviz_time:.2f}s, SVG load={svg_load_time:.2f}s"
            )
        except Exception as e:
            print(f"Error refreshing diagram: {e}", file=sys.stderr)
            QMessageBox.warning(self, "Diagram Error", str(e))
        finally:
            # Always reset the refreshing flag
            self._refreshing = False

    def toggle_show_filtered(self):
        """Toggle whether to show only filtered tables"""
        self.show_only_filtered = self.toolbar_manager.show_filtered_action.isChecked()

        # Remember current filter
        current_filter = self.filter_text

        # Only refresh if we have a filter and tables
        if hasattr(self, "tables") and (current_filter or not self.show_only_filtered):
            # Refresh with current filter
            self.refresh_diagram()

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
        cleanup_temp_files(self.temp_files)
        self.temp_files = []

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
            except Exception as e:
                print(f"Error updating status bar: {e}", file=sys.stderr)
                self.status_bar_manager.update_connection_info()
        else:
            self.status_bar_manager.update_connection_info()

    def on_filter_changed(self, text):
        """Store filter text but don't apply until Enter is pressed"""
        self.filter_text = text.strip()

    def apply_filter(self):
        """Apply the current filter to the tables"""
        # Clear cache when filter changes
        self._diagram_cache = {}

        # Reset refresh counter on deliberate refresh
        self._refresh_counter = 0

        # Block signals on the tree widget
        self.table_tree.blockSignals(True)

        # Store the original auto-refresh state but disable it
        old_auto_refresh = self.auto_refresh
        self.auto_refresh = False

        # Initialize old_cursor before try block
        old_cursor = self.cursor()

        try:
            # Update filtered data
            self.update_filtered_tables()

            # Update tree highlights
            self.highlight_matching_tables_in_tree()

            # Show wait cursor
            self.setCursor(Qt.WaitCursor)
            QCoreApplication.processEvents()

            # Add logging
            print(f"Filter applied: {self.filter_text!r}")

            # Now perform a single diagram refresh
            self.refresh_diagram()
        finally:
            # Restore cursor
            self.setCursor(old_cursor)

            # Restore auto-refresh setting
            self.auto_refresh = old_auto_refresh

            # Unblock signals on the tree widget
            self.table_tree.blockSignals(False)

    def update_filtered_tables(self):
        """Update the lists of tables and fields that match the filter"""
        self.matching_tables = set()
        self.matching_fields = {}

        if not self.filter_text or not hasattr(self, "tables"):
            return

        filter_text = self.filter_text.lower()
        for table_name, table in self.tables.items():
            # Check if table name matches
            if filter_text in table_name.lower():
                self.matching_tables.add(table_name)

            # Check if any columns match
            matching_columns = []
            for column in table.columns:
                if filter_text in column.name.lower():
                    matching_columns.append(column.name)
            if matching_columns:
                self.matching_fields[table_name] = matching_columns
                # Also add to matching tables if any field matches
                self.matching_tables.add(table_name)

    def highlight_matching_tables_in_tree(self):
        """Highlight matching tables in the tree view"""
        if not hasattr(self, "table_tree"):
            return

        # Temporarily disable auto-refresh
        old_auto_refresh = self.auto_refresh
        self.auto_refresh = False

        # Block all signals from the tree widget during updates
        self.table_tree.blockSignals(True)
        self.table_tree.setUpdatesEnabled(False)

        try:
            # Reset all items to normal style
            iterator = QTreeWidgetItemIterator(self.table_tree)
            while iterator.value():
                item = iterator.value()
                # Reset foreground color to default
                item.setForeground(0, self.palette().text())
                # Reset to normal font
                normal_font = QFont(self.font())
                normal_font.setBold(False)  # Explicitly set not bold
                item.setFont(0, normal_font)
                iterator += 1

            # If no filter or no matches, we're done
            if not self.filter_text or not self.matching_tables:
                return

            # Set matching tables to light blue and bold
            bold_font = QFont(self.font())
            bold_font.setBold(True)

            # Use light blue for highlighting in the tree view
            highlight_color = QColor(30, 144, 255)  # Dodger blue

            iterator = QTreeWidgetItemIterator(self.table_tree)
            while iterator.value():
                item = iterator.value()
                table_name = item.text(0)

                if table_name in self.matching_tables:
                    item.setForeground(0, highlight_color)
                    item.setFont(0, bold_font)

                iterator += 1
        finally:
            # Always restore signals and updates
            self.table_tree.setUpdatesEnabled(True)
            self.table_tree.blockSignals(False)

            # Restore auto-refresh setting
            self.auto_refresh = old_auto_refresh

    def show_only_filtered_tables(self):
        """Show only the tables matching the current filter"""
        # Check if we have a filter and tables
        if not hasattr(self, "tables") or not self.matching_tables:
            QMessageBox.information(
                self,
                "Filter Required",
                "Please enter a filter first to select matching tables.",
            )
            return

        # Start by blocking signals to prevent recursive refreshes
        self.table_tree.blockSignals(True)
        self.auto_refresh = False

        try:
            # First deselect all tables
            iterator = QTreeWidgetItemIterator(self.table_tree)
            while iterator.value():
                item = iterator.value()
                item.setCheckState(0, Qt.Unchecked)
                iterator += 1

            # Now select only the filtered tables
            iterator = QTreeWidgetItemIterator(self.table_tree)
            while iterator.value():
                item = iterator.value()
                if item.text(0) in self.matching_tables:
                    # Add to last check state to prevent refresh loops
                    self._last_check_state[item] = Qt.Checked
                    item.setCheckState(0, Qt.Checked)
                iterator += 1

            # Clear the filter after applying it to the selection
            self.filter_text = ""
            self.toolbar_manager.filter_edit.clear()

            # Reset the highlighting
            self.matching_tables = set()
            self.matching_fields = {}
            self.highlight_matching_tables_in_tree()

            # Refresh with the new selection
            self.refresh_diagram()

        finally:
            # Always restore signals
            self.auto_refresh = True
            self.table_tree.blockSignals(False)

            # Update status bar to show the selection change
            self.update_status_bar()

    def add_filtered_tables(self):
        """Add the current filtered tables to the selection without clearing existing selection"""
        # Check if we have a filter and tables
        if not hasattr(self, "tables") or not self.matching_tables:
            QMessageBox.information(
                self,
                "Filter Required",
                "Please enter a filter first to select matching tables.",
            )
            return

        # Start by blocking signals to prevent recursive refreshes
        self.table_tree.blockSignals(True)
        self.auto_refresh = False

        try:
            # Select the filtered tables without deselecting others first
            iterator = QTreeWidgetItemIterator(self.table_tree)
            while iterator.value():
                item = iterator.value()
                if item.text(0) in self.matching_tables:
                    # Add to last check state to prevent refresh loops
                    self._last_check_state[item] = Qt.Checked
                    item.setCheckState(0, Qt.Checked)
                iterator += 1

            # Keep the filter active (do not clear it)
            # This preserves the highlight effect

            # Refresh with the new selection
            self.refresh_diagram()

        finally:
            # Always restore signals
            self.auto_refresh = True
            self.table_tree.blockSignals(False)

            # Update status bar to show the selection change
            self.update_status_bar()

    def _on_prefix_edit(self):
        """Called when prefix edit box is activated via Enter key"""
        # Show wait cursor
        old_cursor = self.cursor()
        self.setCursor(Qt.WaitCursor)
        # Force processing of pending events so cursor change is shown
        QCoreApplication.processEvents()

        try:
            print(f"Prefix edit: {self.status_bar_manager.get_prefix()!r}")
            # Just refresh directly instead of going through handlers
            self.refresh_diagram()
        finally:
            # Always restore the cursor
            self.setCursor(old_cursor)

    def toggle_dark_canvas(self):
        """Toggle dark canvas mode for the diagram view"""
        dark_mode_enabled = self.toolbar_manager.dark_canvas_action.isChecked()
        self.diagram_view.set_dark_canvas(dark_mode_enabled)

        # Force diagram regeneration when dark mode changes
        # This is needed to update arrow colors and other DOT-generated elements
        print(f"Dark canvas mode toggled: {dark_mode_enabled}")

        # Clear the cache to force a refresh with the new dark mode setting
        if hasattr(self, "_diagram_cache"):
            self._diagram_cache = {}

        # Refresh the diagram to apply dark mode changes
        self.refresh_diagram()

    def setup_tree_view(self):
        """Setup tree view selection handling"""
        self.table_tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        self.table_tree.itemClicked.connect(self.on_tree_item_clicked)

    def on_tree_selection_changed(self):
        """Handle tree view selection changes and update the diagram accordingly"""
        self.update_diagram_from_selection()

    def on_tree_item_clicked(self, item, column):
        """Additional handler to ensure clicked items are properly selected and added to diagram"""
        # Make sure the item is selected (sometimes selection events don't trigger properly)
        if not item.isSelected():
            item.setSelected(True)

        # Force update of the diagram based on the current selection
        self.update_diagram_from_selection()

    def update_diagram_from_selection(self):
        """Update the diagram based on the current tree selection"""
        selected_tables = []

        # Get all selected items
        for item in self.table_tree.selectedItems():
            # Only consider table items (not category/group items)
            if hasattr(item, "table_name") and item.table_name:
                selected_tables.append(item.table_name)

        if selected_tables:
            # Update the selected tables in the model
            self.tables.update(selected_tables)

            # Refresh the diagram to show the newly selected tables
            self.refresh_diagram()

            # Log for debugging
            print(f"Added tables to diagram: {selected_tables}")


def main():
    app = QApplication(sys.argv)

    # Monitor refresh calls during development to catch infinite loops
    # Uncomment to debug refresh loops
    # from debug_tools import monitor_method
    # monitor_method(MainWindow, "refresh_diagram")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
