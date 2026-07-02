"""Окно входа."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox,
)

from auth import AuthService
from utils.logger import get_logger

logger = get_logger(__name__)


class LoginWindow(QWidget):
    """Окно логина. После успешного входа эмитит signal `logged_in`."""

    logged_in = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureWatch — Вход")
        self.setFixedSize(380, 240)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)

        title = QLabel("🔐 Вход в систему")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin")
        form.addRow("Логин:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("••••••••")
        form.addRow("Пароль:", self.password_input)

        layout.addLayout(form)

        self.login_btn = QPushButton("Войти")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        # Enter в любом поле = клик по «Войти»
        self.username_input.returnPressed.connect(self.login_btn.click)
        self.password_input.returnPressed.connect(self.login_btn.click)

    def _on_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните логин и пароль")
            return

        user = AuthService.login(username, password)

        if user is None:
            QMessageBox.critical(
                self, "Ошибка входа",
                "Неверный логин или пароль,\nлибо аккаунт заблокирован.",
            )
            self.password_input.clear()
            self.password_input.setFocus()
            return

        self.logged_in.emit()
        self.close()