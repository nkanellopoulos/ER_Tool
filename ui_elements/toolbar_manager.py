import os
import sys
import tempfile

from PySide6.QtCore import QSize
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QSizePolicy


class ToolbarManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.toolbar = main_window.addToolBar("Tools")
        self.toolbar.setIconSize(QSize(32, 32))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # Initialize filter edit field
        self.filter_edit = QLineEdit(main_window)
        self.filter_edit.setPlaceholderText("Filter tables and fields...")
        self.filter_edit.setClearButtonEnabled(True)
        # Set stricter width constraints for filter textbox
        self.filter_edit.setMinimumWidth(200)
        self.filter_edit.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        # Create all actions
        self._create_actions()
        # Add actions to toolbar
        self._setup_toolbar()

        # Initialize is_dark_mode flag
        self.is_dark_mode = main_window.palette().window().color().lightness() < 128

    def _create_actions(self):
        """Create all toolbar actions"""
        # Database actions
        self.connect_action = self._create_action(
            "Connect to Database",
            "database",
            "Ctrl+B",
            self.main_window.show_connection_dialog,
        )

        # View actions
        self.zoom_in_action = self._create_action(
            "Zoom In",
            "zoom-in",
            "Ctrl+=",
            lambda: (
                self.main_window.diagram_view.scale(1.15, 1.15)
                if self.main_window.diagram_view.zoom_level * 1.15 <= 3.0
                else None
            ),
        )
        self.zoom_out_action = self._create_action(
            "Zoom Out",
            "zoom-out",
            "Ctrl+-",
            lambda: (
                self.main_window.diagram_view.scale(0.87, 0.87)
                if self.main_window.diagram_view.zoom_level * 0.87 >= 0.08
                else None
            ),
        )
        self.zoom_100_action = self._create_action(
            "100%", "zoom-100", "Ctrl+1", self.main_window._zoom_100
        )
        self.fit_action = self._create_action(
            "Fit View", "zoom-fit-best", "Ctrl+0", self.main_window.fit_view
        )

        # Add a dark canvas mode action
        self.dark_canvas_action = self._create_action(
            "Dark Canvas",
            "night-mode",  # You may need to add this icon
            "Ctrl+Shift+D",
            self.main_window.toggle_dark_canvas,
        )
        self.dark_canvas_action.setCheckable(True)
        self.dark_canvas_action.setChecked(False)

        # Selection actions
        self.select_all_action = self._create_action(
            "Select All",
            "dialog-ok-apply",
            "Ctrl+A",
            self.main_window.select_all_tables,
        )
        self.deselect_all_action = self._create_action(
            "Deselect All", "edit-clear", "Ctrl+D", self.main_window.deselect_all_tables
        )

        # Diagram actions
        self.refresh_action = self._create_action(
            "Refresh", "view-refresh", "F5", self.main_window.refresh_diagram
        )
        self.export_action = self._create_action(
            "Export", "document-save", "Ctrl+S", self.main_window.export_diagram
        )
        self.show_referenced_action = self._create_action(
            "Show Referenced Tables", "dialog-ok", "", self.main_window.refresh_diagram
        )
        self.show_referenced_action.setCheckable(True)

        # Overview mode action
        self.overview_action = self._create_action(
            "Overview Mode", "airplane", "", self.main_window.refresh_diagram
        )
        self.overview_action.setCheckable(True)

        # Change "Show only filtered" to a simple action button (not checkable)
        self.show_filtered_action = self._create_action(
            "Show Only Filtered",
            "view-filter",
            "Ctrl+F",
            self.main_window.show_only_filtered_tables,
        )

        # Add a new "Add Filtered" button
        self.add_filtered_action = self._create_action(
            "Add Filtered",
            "list-add",  # Using a standard add icon
            "Ctrl+Shift+F",
            self.main_window.add_filtered_tables,
        )

    def _setup_toolbar(self):
        """Setup toolbar layout"""
        # Filter section first
        self.toolbar.addWidget(QLabel("Filter: "))
        self.toolbar.addWidget(self.filter_edit)
        self.toolbar.addAction(self.show_filtered_action)
        self.toolbar.addAction(self.add_filtered_action)  # Add the new button
        self.toolbar.addSeparator()

        # Database section
        self.toolbar.addWidget(QLabel("Database: "))
        self.toolbar.addAction(self.connect_action)
        self.toolbar.addSeparator()

        # View section
        self.toolbar.addWidget(QLabel("View: "))
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.zoom_100_action)
        self.toolbar.addAction(self.fit_action)
        self.toolbar.addAction(self.dark_canvas_action)  # Add dark canvas option
        self.toolbar.addSeparator()

        # Selection section
        self.toolbar.addWidget(QLabel("Selection: "))
        self.toolbar.addAction(self.select_all_action)
        self.toolbar.addAction(self.deselect_all_action)
        self.toolbar.addSeparator()

        # Diagram section
        self.toolbar.addWidget(QLabel("Diagram: "))
        self.toolbar.addAction(self.refresh_action)
        self.toolbar.addAction(self.export_action)
        self.toolbar.addAction(self.show_referenced_action)
        self.toolbar.addAction(self.overview_action)

    def _create_action(self, text: str, icon_name: str, shortcut: str, slot) -> QAction:
        """Helper to create QAction with icon"""
        action = QAction(text, self.main_window)
        action.setShortcut(shortcut)
        action.triggered.connect(slot)
        action.setIcon(self._load_icon(icon_name))
        return action

    def _load_icon(self, name: str) -> QIcon:
        """Load icon from file with dark mode support"""
        icon = QIcon()
        is_dark = self.main_window.palette().window().color().lightness() < 128

        # Try to load icon from different locations
        for icon_dir in [
            os.path.join(os.path.dirname(__file__), "icons"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons"),
        ]:
            path = os.path.join(icon_dir, f"{name}.svg")
            if os.path.exists(path):
                # Read SVG content
                with open(path, "r") as f:
                    svg_content = f.read()

                # Replace color based on theme
                color = "#F1F1F1" if is_dark else "#000000"
                if "fill" in svg_content:
                    svg_content = svg_content.replace(
                        'fill="currentColor"', f'fill="{color}"'
                    )
                    svg_content = svg_content.replace(
                        "stroke:currentColor", f"stroke:{color}"
                    )
                    svg_content = svg_content.replace('fill="#fff"', f'fill="{color}"')
                    svg_content = svg_content.replace(
                        'fill="#ffffff"', f'fill="{color}"'
                    )

                # Create temporary file with modified SVG
                with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
                    tmp.write(svg_content.encode())
                    tmp_path = tmp.name
                    self.main_window.temp_files.append(tmp_path)  # Add to cleanup list

                # Add the modified icon for all states
                icon.addFile(tmp_path, QSize(), QIcon.Normal, QIcon.Off)
                icon.addFile(tmp_path, QSize(), QIcon.Normal, QIcon.On)
                icon.addFile(tmp_path, QSize(), QIcon.Selected, QIcon.Off)
                icon.addFile(tmp_path, QSize(), QIcon.Selected, QIcon.On)
                return icon

        print(f"Warning: Icon not found: {name}.svg", file=sys.stderr)
        return icon

    def update_icons(self, exclude_canvas_button=False):
        """
        Update toolbar icons to match the current palette

        Args:
            exclude_canvas_button: If True, don't update the dark canvas button
        """
        # Update is_dark_mode flag based on application palette
        self.is_dark_mode = (
            self.main_window.palette().window().color().lightness() < 128
        )

        # Store canvas button state if needed
        dark_canvas_checked = None
        if exclude_canvas_button and hasattr(self, "dark_canvas_action"):
            dark_canvas_checked = self.dark_canvas_action.isChecked()

        # Instead of recreating actions, just update their icons
        for action_name in dir(self):
            if action_name.endswith("_action") and hasattr(self, action_name):
                action = getattr(self, action_name)
                if isinstance(action, QAction):
                    # Only exclude updating the state of the dark canvas button
                    # but still update its icon to match the theme
                    icon_name = self._get_icon_name_for_action(action)
                    if icon_name:
                        action.setIcon(self._load_icon(icon_name))

        # Restore dark canvas button state if needed
        if (
            exclude_canvas_button
            and hasattr(self, "dark_canvas_action")
            and dark_canvas_checked is not None
        ):
            self.dark_canvas_action.setChecked(dark_canvas_checked)

    def _get_icon_name_for_action(self, action):
        """Map actions to icon names"""
        # Create a mapping of action text to icon names
        icon_map = {
            "Connect to Database": "database",
            "Zoom In": "zoom-in",
            "Zoom Out": "zoom-out",
            "100%": "zoom-100",
            "Fit View": "zoom-fit-best",
            "Dark Canvas": "night-mode",
            "Select All": "dialog-ok-apply",
            "Deselect All": "edit-clear",
            "Refresh": "view-refresh",
            "Export": "document-save",
            "Show Referenced Tables": "dialog-ok",
            "Overview Mode": "airplane",
            "Show Only Filtered": "view-filter",
            "Add Filtered": "list-add",
        }

        # Try to find the icon name from the map
        if action.text() in icon_map:
            return icon_map[action.text()]

        # If not found, try to derive from the action name
        for action_name in dir(self):
            if action_name.endswith("_action") and getattr(self, action_name) == action:
                # Convert action_name to likely icon name (e.g., zoom_in_action -> zoom-in)
                base_name = action_name[:-7]  # Remove '_action'
                icon_name = base_name.replace("_", "-")
                return icon_name

        return None
