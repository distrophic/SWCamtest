"""Главное окно приложения."""

from datetime import datetime
from pathlib import Path

import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QStatusBar, QVBoxLayout, QWidget,
)

from auth import AuthService, Session
from config import CAMERA, RECORDINGS_DIR, SNAPSHOTS_DIR
from core.camera_stream import CameraStream
from core.detections import entities_only, persons_only
from core.pipeline import Pipeline
from core.recordings import list_recording_files, rotate_recordings
from core.validators import Validators
from core.zone import format_zone
from database.repositories import EventRepository, SettingsRepository
from gui.widgets.video_widget import VideoWidget
from gui.windows.password_dialog import PasswordDialog
from gui.windows.user_dialog import UserDialog
from utils.logger import get_logger

logger = get_logger(__name__)


def _spin_buttons_only(spin: QSpinBox, text: str) -> None:
    """Стрелки меняют число. В само поле курсор не ставится."""
    spin.setSpecialValueText(text)
    edit = spin.lineEdit()
    edit.setReadOnly(True)
    edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    width = spin.fontMetrics().horizontalAdvance(text) + 40
    spin.setMinimumWidth(width)


def _beep() -> None:
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        QApplication.beep()


class MainWindow(QMainWindow):
    """Главное окно после успешного входа."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureWatch")
        self.resize(1100, 820)

        self.tiles: list[VideoWidget] = []
        self.video_widget: VideoWidget | None = None
        self._previews: list[CameraStream | None] = [None, None, None, None]
        self._slots = [SettingsRepository.grid_source(index) for index in range(4)]
        self._selected = SettingsRepository.grid_selected()
        self._reviewing = False
        self._return_source = ""
        self._grid_mode = False
        self._person_active = False
        self._entity_active = False
        self._logged_connect = False
        self._camera_up = False
        self._shutting_down = False

        self._build_ui()
        self._load_saved_controls()
        self._apply_access()
        self._update_status()

        self.pipeline = Pipeline(self)
        self._bind_pipeline()
        source = self._parsed_slot(self._selected)
        if source is None:
            self.pipeline.start(CAMERA.source, self.conf_spin.value(), open_camera=False)
        else:
            self.pipeline.start(source, self.conf_spin.value())
        self.pipeline.set_zone(SettingsRepository.zone(self._selected))
        self._restart_previews()
        removed = self._rotate_recordings()
        self._refresh_events()
        self._refresh_recordings()
        if removed:
            self._log_event("recording", f"Удалено старых записей: {removed}")

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        header = QHBoxLayout()
        user = Session.current_user()
        username = user.username if user is not None else "—"
        role = user.role if user is not None else "—"
        greeting = QLabel(f"Добро пожаловать, <b>{username}</b> ({role})")
        greeting.setStyleSheet("font-size: 14px;")
        header.addWidget(greeting)
        header.addStretch()

        self.fps_label = QLabel("FPS: —")
        self.fps_label.setStyleSheet("color: #6c6; font-family: monospace;")
        header.addWidget(self.fps_label)

        self.detector_label = QLabel("детектор: —")
        self.detector_label.setStyleSheet("color: #888; font-family: monospace;")
        header.addWidget(self.detector_label)

        self.rec_label = QLabel("idle")
        self.rec_label.setStyleSheet("color: #888; font-family: monospace;")
        header.addWidget(self.rec_label)

        self.connection_label = QLabel("offline")
        self.connection_label.setStyleSheet("color: #c66; font-weight: bold;")
        header.addWidget(self.connection_label)

        self.users_btn = QPushButton("Пользователь")
        self.users_btn.clicked.connect(self._on_create_user)
        header.addWidget(self.users_btn)

        self.password_btn = QPushButton("Пароль")
        self.password_btn.clicked.connect(self._on_change_password)
        header.addWidget(self.password_btn)

        self.logout_btn = QPushButton("Выйти")
        self.logout_btn.clicked.connect(self._on_logout)
        header.addWidget(self.logout_btn)

        layout.addLayout(header)

        self.alert_label = QLabel("ЧЕЛОВЕК")
        self.alert_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alert_label.setStyleSheet(
            "background-color: #c33; color: white; font-weight: bold; padding: 4px;"
        )
        self.alert_label.hide()
        layout.addWidget(self.alert_label)

        self.entity_label = QLabel("СУЩНОСТЬ")
        self.entity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.entity_label.setStyleSheet(
            "background-color: #e80; color: black; font-weight: bold; padding: 4px;"
        )
        self.entity_label.hide()
        layout.addWidget(self.entity_label)

        grid = QGridLayout()
        grid.setSpacing(6)
        for index in range(4):
            tile = VideoWidget()
            tile.setMinimumSize(320, 180)
            tile.activated.connect(lambda i=index: self._select_slot(i))
            tile.zone_changed.connect(self._on_zone_drawn)
            self.tiles.append(tile)
            grid.addWidget(tile, index // 2, index % 2)
        self._camera_grid = grid
        self.video_widget = self.tiles[self._selected]
        self._mark_selected()
        layout.addLayout(grid, stretch=1)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Источник:"))
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText(
            "0, rtsp://..., http://..., файл, synthetic или simulator"
        )
        source_row.addWidget(self.source_edit, stretch=1)

        self.connect_btn = QPushButton("Подключить")
        self.connect_btn.clicked.connect(self._on_connect_source)
        source_row.addWidget(self.connect_btn)

        self.simulator_btn = QPushButton("Нет камеры")
        self.simulator_btn.clicked.connect(self._on_simulator)
        source_row.addWidget(self.simulator_btn)

        source_row.addWidget(QLabel("Порог:"))
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.05, 0.95)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setDecimals(2)
        self.conf_spin.valueChanged.connect(self._on_conf_changed)
        source_row.addWidget(self.conf_spin)

        self.snapshot_btn = QPushButton("Снимок")
        self.snapshot_btn.clicked.connect(self._on_snapshot)
        source_row.addWidget(self.snapshot_btn)

        source_row.addWidget(QLabel("Хранить, дней:"))
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(0, 365)
        _spin_buttons_only(self.retention_spin, "не удалять")
        self.retention_spin.valueChanged.connect(self._on_retention_changed)
        source_row.addWidget(self.retention_spin)

        source_row.addWidget(QLabel("Объём, ГБ:"))
        self.retention_gb_spin = QSpinBox()
        self.retention_gb_spin.setRange(0, 2000)
        _spin_buttons_only(self.retention_gb_spin, "без лимита")
        self.retention_gb_spin.valueChanged.connect(self._on_retention_gb_changed)
        source_row.addWidget(self.retention_gb_spin)
        layout.addLayout(source_row)

        controls = QHBoxLayout()
        self.rec_btn = QPushButton("Начать запись")
        self.rec_btn.setCheckable(True)
        self.rec_btn.setMinimumWidth(180)
        self.rec_btn.setStyleSheet(
            "QPushButton { padding: 8px 16px; font-weight: bold; }"
            "QPushButton:checked { background-color: #c33; color: white; }"
        )
        self.rec_btn.toggled.connect(self._on_rec_btn_toggled)
        controls.addWidget(self.rec_btn)

        self.view_mode_btn = QPushButton("Сетка")
        self.view_mode_btn.clicked.connect(self._toggle_view_mode)
        controls.addWidget(self.view_mode_btn)

        self.auto_checkbox = QCheckBox("Авто-запись по детекции")
        self.auto_checkbox.setStyleSheet("padding: 4px;")
        self.auto_checkbox.toggled.connect(self._on_auto_toggled)
        controls.addWidget(self.auto_checkbox)

        self.zone_btn = QPushButton("Зона")
        self.zone_btn.setCheckable(True)
        self.zone_btn.toggled.connect(self._on_zone_arm)
        controls.addWidget(self.zone_btn)

        self.clear_zone_btn = QPushButton("Сброс зоны")
        self.clear_zone_btn.clicked.connect(self._on_zone_clear)
        controls.addWidget(self.clear_zone_btn)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.clicked.connect(self._on_pause)
        self.pause_btn.hide()
        controls.addWidget(self.pause_btn)

        self.live_btn = QPushButton("К камере")
        self.live_btn.clicked.connect(lambda: self._leave_review())
        self.live_btn.hide()
        controls.addWidget(self.live_btn)
        controls.addStretch()
        layout.addLayout(controls)

        lists = QHBoxLayout()
        events_col = QVBoxLayout()
        events_col.addWidget(QLabel("Журнал событий"))
        self.events_list = QListWidget()
        self.events_list.setMaximumHeight(120)
        events_col.addWidget(self.events_list)
        lists.addLayout(events_col, stretch=1)

        recordings_col = QVBoxLayout()
        recordings_col.addWidget(QLabel("Записи"))
        self.recordings_list = QListWidget()
        self.recordings_list.setMaximumHeight(120)
        self.recordings_list.itemClicked.connect(self._on_recording_clicked)
        self.recordings_list.itemDoubleClicked.connect(self._on_recording_play)
        recordings_col.addWidget(self.recordings_list)
        lists.addLayout(recordings_col, stretch=1)
        layout.addLayout(lists)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self._apply_view_mode()

    def _load_saved_controls(self) -> None:
        confidence = SettingsRepository.confidence()
        self.source_edit.setText(self._slots[self._selected])
        self.conf_spin.blockSignals(True)
        self.conf_spin.setValue(confidence)
        self.conf_spin.blockSignals(False)
        self.retention_spin.blockSignals(True)
        self.retention_spin.setValue(SettingsRepository.retention_days())
        self.retention_spin.blockSignals(False)
        self.retention_gb_spin.blockSignals(True)
        self.retention_gb_spin.setValue(SettingsRepository.retention_gb())
        self.retention_gb_spin.blockSignals(False)
        self.tiles[self._selected].set_zone(SettingsRepository.zone(self._selected))

    def _current_source(self) -> int | str:
        return Validators.parse_camera_source(self.source_edit.text())

    def _can_operate(self) -> bool:
        return Session.has_role("admin", "operator")

    def _apply_access(self) -> None:
        operate = self._can_operate()
        self.source_edit.setEnabled(operate)
        self.connect_btn.setEnabled(operate)
        self.simulator_btn.setEnabled(operate)
        self.conf_spin.setEnabled(operate)
        self.snapshot_btn.setEnabled(operate)
        self.rec_btn.setEnabled(operate and self._camera_up and not self._reviewing)
        self.auto_checkbox.setEnabled(operate and self._camera_up and not self._reviewing)
        self.zone_btn.setEnabled(operate and not self._reviewing)
        self.clear_zone_btn.setEnabled(operate and not self._reviewing)
        self.retention_spin.setEnabled(operate)
        self.retention_gb_spin.setEnabled(operate)
        self.users_btn.setVisible(Session.has_role("admin"))

    def _bind_pipeline(self) -> None:
        self.pipeline.frame_ready.connect(self._on_live_frame)
        self.pipeline.fps_updated.connect(self._on_fps)
        self.pipeline.status.connect(self._on_status)
        self.pipeline.error.connect(self._on_camera_error)
        self.pipeline.camera_available.connect(self._on_camera_available)
        self.pipeline.detector_ready.connect(self._on_detector_ready)
        self.pipeline.detector_failed.connect(self._on_detector_error)
        self.pipeline.detections_ready.connect(self._on_detections)
        self.pipeline.recording_started.connect(self._on_recording_started)
        self.pipeline.recording_stopped.connect(self._on_recording_stopped)

    def _on_live_frame(self, frame: object) -> None:
        self.tiles[self._selected].update_frame(frame)

    def _on_fps(self, fps: float) -> None:
        self.fps_label.setText(f"FPS: {fps:5.1f}")

    def _on_status(self, msg: str) -> None:
        logger.info(f"Камера: {msg}")
        if "подключена" in msg.lower():
            self.connection_label.setText("online")
            self.connection_label.setStyleSheet("color: #6c6; font-weight: bold;")
            if not self._logged_connect:
                self._log_event("camera", msg)
                self._logged_connect = True
        elif "отключена" in msg.lower():
            self.connection_label.setText("offline")
            self.connection_label.setStyleSheet("color: #c66; font-weight: bold;")
        self.statusBar().showMessage(msg, 3000)

    def _on_camera_available(self, available: bool) -> None:
        self._camera_up = available
        if not available:
            self.pipeline.request_manual(False)
            self.pipeline.set_auto_mode(False)
            self._clear_recording_controls()
        self._apply_access()

    def _clear_recording_controls(self) -> None:
        self.rec_btn.blockSignals(True)
        self.auto_checkbox.blockSignals(True)
        self.rec_btn.setChecked(False)
        self.rec_btn.setText("Начать запись")
        self.auto_checkbox.setChecked(False)
        self.rec_btn.blockSignals(False)
        self.auto_checkbox.blockSignals(False)

    def _on_camera_error(self, msg: str) -> None:
        logger.warning(f"Камера: {msg}")
        self.statusBar().showMessage(msg, 5000)
        if "Превышен лимит" in msg:
            self._logged_connect = False
            self._log_event("camera", msg)
            self._clear_recording_controls()

    def _on_detector_ready(self) -> None:
        logger.info("Детектор готов к работе.")
        self.detector_label.setText("детектор: ready")
        self.detector_label.setStyleSheet("color: #6c6; font-family: monospace;")
        self.statusBar().showMessage("Детектор готов", 3000)

    def _on_detector_error(self, msg: str) -> None:
        logger.error(f"Детектор: {msg}")
        self.detector_label.setText("детектор: недоступен")
        self.detector_label.setStyleSheet("color: #c66; font-family: monospace;")
        self.statusBar().showMessage(f"Детектор недоступен: {msg}", 5000)
        self._log_event("detector", msg)

    def _on_detections(self, boxes: list) -> None:
        self.tiles[self._selected].set_detections(boxes)
        persons = persons_only(boxes)
        entities = entities_only(boxes)
        if persons and not self._person_active:
            self._log_event("detection", f"Обнаружено людей: {len(persons)}")
            self.alert_label.show()
            _beep()
        elif not persons and self._person_active:
            self.alert_label.hide()
        self._person_active = bool(persons)
        if entities and not self._entity_active:
            self._log_event("detection", f"Сущностей: {len(entities)}")
            self.entity_label.show()
        elif not entities and self._entity_active:
            self.entity_label.hide()
        self._entity_active = bool(entities)

    def _on_rec_btn_toggled(self, checked: bool) -> None:
        if not self._can_operate():
            self._clear_recording_controls()
            return
        if not self.pipeline.request_manual(checked):
            self.rec_btn.blockSignals(True)
            self.rec_btn.setChecked(False)
            self.rec_btn.blockSignals(False)
            return
        self.rec_btn.setText("Остановить запись" if checked else "Начать запись")

    def _on_auto_toggled(self, checked: bool) -> None:
        if not self._can_operate():
            self._clear_recording_controls()
            return
        if not self.pipeline.set_auto_mode(checked):
            self.auto_checkbox.blockSignals(True)
            self.auto_checkbox.setChecked(False)
            self.auto_checkbox.blockSignals(False)
            return
        status = "включена" if checked else "выключена"
        self.statusBar().showMessage(f"Авто-запись {status}", 2000)

    def _on_recording_started(self, path: str) -> None:
        logger.info(f"REC: {path}")
        self.rec_label.setText("REC")
        self.rec_label.setStyleSheet("color: #c66; font-family: monospace; font-weight: bold;")
        self.statusBar().showMessage(f"Запись: {path}", 3000)
        self._log_event("recording", f"Запись начата: {path}")

    def _on_recording_stopped(self, path: str) -> None:
        logger.info(f"STOP: {path}")
        self.rec_label.setText("idle")
        self.rec_label.setStyleSheet("color: #888; font-family: monospace;")
        self.statusBar().showMessage(f"Сохранено: {path}", 3000)
        self._log_event("recording", f"Запись остановлена: {path}")
        self._rotate_recordings()
        self._refresh_recordings()

    def _on_simulator(self) -> None:
        if not self._can_operate():
            return
        self.source_edit.setText("simulator")
        self._on_connect_source()

    def _on_connect_source(self) -> None:
        if not self._can_operate():
            return
        text = self.source_edit.text().strip()
        if not text:
            self._leave_review(restore=False)
            self._slots[self._selected] = ""
            SettingsRepository.set(f"grid_source_{self._selected}", "")
            self._clear_recording_controls()
            self._restart_previews()
            self.pipeline.blank()
            self._apply_access()
            self.statusBar().showMessage(f"Ячейка {self._selected + 1} пустая", 3000)
            return
        parsed = Validators.parse_camera_source(text)
        if not Validators.validate_camera_source(parsed):
            QMessageBox.warning(
                self,
                "Источник",
                "Укажите индекс камеры, RTSP/HTTP URL, путь к видеофайлу, synthetic или simulator.",
            )
            return
        self._leave_review(restore=False)
        self._clear_recording_controls()
        text = str(parsed)
        self._slots[self._selected] = text
        SettingsRepository.set(f"grid_source_{self._selected}", text)
        SettingsRepository.set("camera_source", text)
        self._restart_previews()
        self.pipeline.set_source(parsed)
        self.statusBar().showMessage(f"Ячейка {self._selected + 1}: {parsed}", 3000)

    def _on_conf_changed(self, value: float) -> None:
        if not self._can_operate():
            return
        self.pipeline.set_confidence(float(value))
        SettingsRepository.set("confidence", f"{float(value):.2f}")

    def _on_snapshot(self) -> None:
        if not self._can_operate() or self.video_widget is None:
            return
        frame = self.video_widget.last_frame()
        if frame is None:
            QMessageBox.information(self, "Снимок", "Нет кадра для сохранения")
            return

        folder = Path(SNAPSHOTS_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{datetime.now():%Y%m%d-%H%M%S}.jpg"
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            QMessageBox.warning(self, "Снимок", "Не удалось закодировать кадр")
            return
        path.write_bytes(encoded.tobytes())
        self.statusBar().showMessage(f"Снимок: {path}", 3000)
        self._log_event("snapshot", f"Снимок сохранён: {path}")

    def _on_retention_changed(self, value: int) -> None:
        if not self._can_operate():
            return
        SettingsRepository.set("retention_days", str(int(value)))

    def _on_retention_gb_changed(self, value: int) -> None:
        if not self._can_operate():
            return
        SettingsRepository.set("retention_gb", str(int(value)))

    def _rotate_recordings(self) -> int:
        return rotate_recordings(
            RECORDINGS_DIR,
            days=SettingsRepository.retention_days(),
            max_bytes=SettingsRepository.retention_gb() * 1024 ** 3,
        )

    def _on_recording_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        self.statusBar().showMessage(str(path), 8000)

    def _on_recording_play(self, item: QListWidgetItem) -> None:
        path = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        if not path.is_file():
            return
        if not self._reviewing:
            self._return_source = self._slots[self._selected]
        self._reviewing = True
        self._clear_recording_controls()
        self._apply_access()
        self.pipeline.set_paused(False)
        self.pause_btn.setText("Пауза")
        self.pause_btn.show()
        self.live_btn.show()
        self._restart_previews()
        self.pipeline.set_source(str(path))
        self.statusBar().showMessage(f"Просмотр: {path}", 8000)

    def _on_pause(self) -> None:
        paused = self.pause_btn.text() == "Пауза"
        self.pipeline.set_paused(paused)
        self.pause_btn.setText("Дальше" if paused else "Пауза")

    def _leave_review(self, restore: bool = True) -> None:
        if not self._reviewing:
            return
        self._reviewing = False
        self.pipeline.set_paused(False)
        self.pause_btn.hide()
        self.live_btn.hide()
        self.pause_btn.setText("Пауза")
        self._restart_previews()
        if not restore:
            return
        source = self._return_source.strip()
        self._apply_access()
        if not source:
            self.pipeline.blank()
            return
        parsed = Validators.parse_camera_source(source)
        self.pipeline.set_source(parsed)

    def _select_slot(self, index: int) -> None:
        if index == self._selected and not self._reviewing:
            return
        self._leave_review(restore=False)
        self._selected = index
        self.video_widget = self.tiles[index]
        SettingsRepository.set("grid_selected", str(index))
        self._mark_selected()
        self._arm_zone(False)
        for tile_index, tile in enumerate(self.tiles):
            if tile_index != index:
                tile.set_detections([])
                tile.set_zone(None)
        zone = SettingsRepository.zone(index)
        self.tiles[index].set_zone(zone)
        self.pipeline.set_zone(zone)
        self.source_edit.setText(self._slots[index])
        self._clear_recording_controls()
        self._person_active = False
        self._entity_active = False
        self.alert_label.hide()
        self.entity_label.hide()
        self._apply_view_mode()
        self._restart_previews()
        source = self._parsed_slot(index)
        if source is None:
            self.pipeline.blank()
        else:
            self.pipeline.set_source(source)
        self._apply_access()

    def _toggle_view_mode(self) -> None:
        self._grid_mode = not self._grid_mode
        self.view_mode_btn.setText("Одна камера" if self._grid_mode else "Сетка")
        self._apply_view_mode()
        self._restart_previews()

    def _apply_view_mode(self) -> None:
        host = self._camera_grid.parentWidget()
        for tile in self.tiles:
            self._camera_grid.removeWidget(tile)
            if host is not None:
                tile.setParent(host)
        if self._grid_mode:
            for index, tile in enumerate(self.tiles):
                tile.setVisible(True)
                self._camera_grid.addWidget(tile, index // 2, index % 2)
            return
        for index, tile in enumerate(self.tiles):
            tile.setVisible(index == self._selected)
        self._camera_grid.addWidget(self.tiles[self._selected], 0, 0, 2, 2)

    def _mark_selected(self) -> None:
        for index, tile in enumerate(self.tiles):
            border = "#6c6" if index == self._selected else "#333"
            tile.setStyleSheet(
                f"background-color: #111; color: #888; border: 2px solid {border};"
            )

    def _parsed_slot(self, index: int):
        text = self._slots[index].strip()
        if not text:
            return None
        parsed = Validators.parse_camera_source(text)
        if not Validators.validate_camera_source(parsed):
            return None
        return parsed

    def _restart_previews(self) -> None:
        for index in range(4):
            self._stop_preview(index)
            if not self._grid_mode or index == self._selected or self._reviewing:
                continue
            source = self._parsed_slot(index)
            if source is None:
                continue
            stream = CameraStream(self.pipeline.camera_config(source))
            stream.frame_ready.connect(self.tiles[index].update_frame)
            stream.error.connect(self._on_camera_error)
            stream.start()
            self._previews[index] = stream

    def _stop_preview(self, index: int) -> None:
        stream = self._previews[index]
        if stream is not None:
            stream.stop()
            self._previews[index] = None

    def _on_zone_arm(self, checked: bool) -> None:
        if not self._can_operate():
            self.zone_btn.blockSignals(True)
            self.zone_btn.setChecked(False)
            self.zone_btn.blockSignals(False)
            return
        self._arm_zone(checked)

    def _arm_zone(self, armed: bool) -> None:
        self.zone_btn.blockSignals(True)
        self.zone_btn.setChecked(armed)
        self.zone_btn.blockSignals(False)
        for index, tile in enumerate(self.tiles):
            tile.set_zone_arm(armed and index == self._selected)

    def _on_zone_drawn(self, zone: tuple) -> None:
        if not self._can_operate():
            return
        SettingsRepository.set(f"zone_{self._selected}", format_zone(zone))
        self.tiles[self._selected].set_zone(zone)
        self.pipeline.set_zone(zone)
        self._arm_zone(False)
        self.statusBar().showMessage("Зона сохранена", 2000)

    def _on_zone_clear(self) -> None:
        if not self._can_operate():
            return
        SettingsRepository.set(f"zone_{self._selected}", "")
        self.tiles[self._selected].set_zone(None)
        self.pipeline.set_zone(None)
        self._arm_zone(False)

    def _stop_previews(self) -> None:
        for index in range(4):
            self._stop_preview(index)

    def _on_change_password(self) -> None:
        user = Session.current_user()
        if user is None:
            return
        PasswordDialog(user, force=False, parent=self).exec()

    def _on_create_user(self) -> None:
        if not Session.has_role("admin"):
            return
        UserDialog(self).exec()

    def _log_event(self, event_type: str, message: str) -> None:
        try:
            EventRepository.add(event_type, message)
        except Exception:
            logger.exception("Не удалось записать событие")
            return
        self._refresh_events()

    def _refresh_events(self) -> None:
        try:
            rows = EventRepository.list_recent(50)
        except Exception:
            logger.exception("Не удалось прочитать журнал")
            return
        self.events_list.clear()
        for row in rows:
            stamp = row.created_at.strftime("%H:%M:%S") if row.created_at else "--:--:--"
            self.events_list.addItem(f"{stamp}  {row.event_type}: {row.message}")

    def _refresh_recordings(self) -> None:
        self.recordings_list.clear()
        try:
            files = list_recording_files(RECORDINGS_DIR)
        except OSError:
            logger.exception("Не удалось прочитать каталог записей")
            return
        for path in files:
            item = QListWidgetItem(f"{path.parent.name}  {path.name}")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.recordings_list.addItem(item)

    def _update_status(self) -> None:
        user = Session.current_user()
        if user is None:
            self.statusBar().showMessage("Нет активной сессии")
            return
        self.statusBar().showMessage(
            f"Пользователь: {user.username}  •  Роль: {user.role}  •  Статус: онлайн"
        )

    def _shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._stop_previews()
        self.pipeline.stop()

    def _on_logout(self) -> None:
        self._shutdown()
        AuthService.logout()
        self.close()

    def closeEvent(self, event):  # noqa: N802
        self._shutdown()
        AuthService.logout()
        super().closeEvent(event)
