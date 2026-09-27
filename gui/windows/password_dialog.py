"""Диалог смены пароля."""

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QVBoxLayout,
)

from auth import AuthService
from database.models import User


class PasswordDialog(QDialog):
    """Смена пароля. В принудительном режиме закрытие без смены отменяет вход."""

    def __init__(self, user: User, force: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.user = user
        self.force = force
        self.setWindowTitle("Смена пароля")
        self.setFixedWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        if self.force:
            note = QLabel(
                "Сейчас используется пароль по умолчанию.\n"
                "Задайте новый пароль, чтобы продолжить."
            )
            note.setWordWrap(True)
            layout.addWidget(note)

        form = QFormLayout()
        self.old_input = QLineEdit()
        self.old_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Текущий пароль:", self.old_input)

        self.new_input = QLineEdit()
        self.new_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Новый пароль:", self.new_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Повтор:", self.confirm_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self) -> None:
        new_password = self.new_input.text()
        if new_password != self.confirm_input.text():
            QMessageBox.warning(self, "Пароль", "Новый пароль и повтор не совпадают")
            return
        if AuthService.is_default_password(new_password):
            QMessageBox.warning(self, "Пароль", "Нельзя оставлять пароль по умолчанию")
            return

        try:
            AuthService.change_password(self.user.id, self.old_input.text(), new_password)
        except ValueError as exc:
            QMessageBox.warning(self, "Пароль", str(exc))
            return

        self.accept()
