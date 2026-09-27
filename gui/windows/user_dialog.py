"""Создание пользователя. Доступно только администратору."""

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QVBoxLayout,
)

from auth import AuthService
from database.repositories import UserRepository


class UserDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Новый пользователь")
        self.setFixedWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.username_input = QLineEdit()
        form.addRow("Логин:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Пароль:", self.password_input)

        self.role_input = QComboBox()
        self.role_input.addItems(list(UserRepository.ALLOWED_ROLES))
        self.role_input.setCurrentText("viewer")
        form.addRow("Роль:", self.role_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self) -> None:
        try:
            AuthService.register(
                self.username_input.text().strip(),
                self.password_input.text(),
                self.role_input.currentText(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Пользователь", str(exc))
            return
        self.accept()
