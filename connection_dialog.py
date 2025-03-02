from PySide6.QtCore import Qt
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QHBoxLayout
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QVBoxLayout


class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Connection")

        # Just make it non-modal and ensure cleanup
        self.setModal(False)
        self.setAttribute(Qt.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # Create all widgets first
        self.db_type = QComboBox()
        self.host = QLineEdit()
        self.port = QLineEdit()
        self.database = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()

        # Database type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Database Type:"))
        self.db_type.addItems(["postgresql", "mysql"])
        type_layout.addWidget(self.db_type)
        layout.addLayout(type_layout)

        # Host
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host:"))
        self.host.setPlaceholderText("localhost")
        host_layout.addWidget(self.host)
        layout.addLayout(host_layout)

        # Port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        port_layout.addWidget(self.port)
        layout.addLayout(port_layout)

        # Database
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database:"))
        db_layout.addWidget(self.database)
        layout.addLayout(db_layout)

        # Username
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("Username:"))
        user_layout.addWidget(self.username)
        layout.addLayout(user_layout)

        # Password
        pass_layout = QHBoxLayout()
        pass_layout.addWidget(QLabel("Password:"))
        self.password.setEchoMode(QLineEdit.Password)
        pass_layout.addWidget(self.password)
        layout.addLayout(pass_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # Connect signals after all widgets are created
        self.connect_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.db_type.currentTextChanged.connect(self._update_port_placeholder)

        # Initialize port placeholder
        self._update_port_placeholder(self.db_type.currentText())

    def _update_port_placeholder(self, db_type: str):
        """Update port placeholder based on database type"""
        default_ports = {"postgresql": "5432", "mysql": "3306"}
        self.port.setPlaceholderText(default_ports.get(db_type, ""))

    def accept(self):
        """Validate inputs before accepting"""
        if not self.host.text():
            self.host.setText(self.host.placeholderText())
        if not self.port.text():
            self.port.setText(self.port.placeholderText())
        if not self.database.text():
            QMessageBox.warning(self, "Validation Error", "Database name is required")
            return
        if not self.username.text():
            QMessageBox.warning(self, "Validation Error", "Username is required")
            return

        super().accept()

    def get_connection_string(self) -> str:
        """Generate connection string from inputs"""
        return (
            f"{self.db_type.currentText()}://{self.username.text()}:"
            + f"{self.password.text()}@{self.host.text()}:{self.port.text()}/"
            + f"{self.database.text()}"
        )

    def set_connection_string(self, conn_string: str):
        """Parse connection string and set dialog fields"""
        if not conn_string:
            return

        try:
            # Parse: dbtype://user:pass@host:port/dbname
            db_type, rest = conn_string.split("://")
            auth, location = rest.split("@")
            user, pwd = auth.split(":")
            host_port, db = location.split("/")
            host, port = host_port.split(":")

            self.db_type.setCurrentText(db_type)
            self.host.setText(host)
            self.port.setText(port)
            self.database.setText(db)
            self.username.setText(user)
            self.password.setText(pwd)
        except:
            pass

    def closeEvent(self, event):
        """Handle window close button"""
        self.reject()
        event.accept()
