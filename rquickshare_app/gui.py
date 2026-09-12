import os
import sys
import subprocess
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QIcon, QFont, QPixmap, QColor, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QDialog, QCheckBox, QComboBox,
    QScrollArea, QFrame, QMenu, QSystemTrayIcon, QListWidget, QListWidgetItem,
    QMessageBox, QApplication, QStyle
)
import rqs_lib
from rquickshare_app.settings import SettingsManager
from rquickshare_app.worker import RQSWorker


class SettingsDialog(QDialog):
    settings_updated = Signal()

    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("RQuickShare Settings")
        self.setMinimumWidth(450)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title_label = QLabel("Settings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Download Path
        dl_layout = QVBoxLayout()
        dl_label = QLabel("Download Location:")
        dl_inner = QHBoxLayout()
        self.dl_path_label = QLabel(self.settings.get("download_path", str(Path.home() / "Downloads")))
        self.dl_path_label.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.dl_path_label.setStyleSheet("padding: 6px; background-color: #f3f4f6; border-radius: 6px;")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_download_path)
        dl_inner.addWidget(self.dl_path_label, 1)
        dl_inner.addWidget(browse_btn)
        dl_layout.addWidget(dl_label)
        dl_layout.addLayout(dl_inner)
        layout.addLayout(dl_layout)

        # Visibility
        vis_layout = QHBoxLayout()
        vis_label = QLabel("Device Visibility:")
        self.vis_combo = QComboBox()
        self.vis_combo.addItem("Visible to Everyone", 1)
        self.vis_combo.addItem("Invisible", 0)
        current_vis = self.settings.get("visibility", 1)
        self.vis_combo.setCurrentIndex(0 if current_vis == 1 else 1)
        vis_layout.addWidget(vis_label)
        vis_layout.addWidget(self.vis_combo)
        layout.addLayout(vis_layout)

        # Checkboxes
        self.autostart_cb = QCheckBox("Start automatically on login")
        self.autostart_cb.setChecked(self.settings.get("autostart", True))
        layout.addWidget(self.autostart_cb)

        self.realclose_cb = QCheckBox("Exit app on window close (instead of minimize to tray)")
        self.realclose_cb.setChecked(self.settings.get("realclose", False))
        layout.addWidget(self.realclose_cb)

        self.startminimized_cb = QCheckBox("Start minimized to tray")
        self.startminimized_cb.setChecked(self.settings.get("startminimized", False))
        layout.addWidget(self.startminimized_cb)

        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

    def browse_download_path(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Downloads Folder", self.dl_path_label.text()
        )
        if directory:
            self.dl_path_label.setText(directory)

    def save_settings(self):
        self.settings.set("download_path", self.dl_path_label.text())
        self.settings.set("visibility", self.vis_combo.currentData())
        self.settings.set("autostart", self.autostart_cb.isChecked())
        self.settings.set("realclose", self.realclose_cb.isChecked())
        self.settings.set("startminimized", self.startminimized_cb.isChecked())
        self.settings_updated.emit()
        self.accept()


class TransferCard(QFrame):
    action_triggered = Signal(str, str)  # (target_id, action)
    clear_triggered = Signal(str)  # (target_id)

    def __init__(self, message_data: dict, parent=None):
        super().__init__(parent)
        self.msg_id = message_data.get("id", "")
        self.data = message_data
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            TransferCard {
                background-color: #ecfdf5;
                border: 1px solid #a7f3d0;
                border-radius: 16px;
                padding: 12px;
                margin-bottom: 8px;
            }
        """)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        meta = self.data.get("meta") or {}
        source = meta.get("source") or {}
        sender_name = source.get("name", "Unknown Device")
        files = meta.get("files") or []
        text_desc = meta.get("text_description")
        text_payload = meta.get("text_payload")
        destination = meta.get("destination")
        pin_code = meta.get("pin_code")
        state = self.data.get("state", "Initial")

        header = QHBoxLayout()
        name_label = QLabel(sender_name)
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        name_label.setFont(name_font)
        header.addWidget(name_label)

        if pin_code:
            pin_badge = QLabel(f"PIN: {pin_code}")
            pin_badge.setStyleSheet("background-color: #d1fae5; color: #065f46; padding: 2px 8px; border-radius: 10px; font-weight: bold;")
            header.addWidget(pin_badge)

        header.addStretch()
        layout.addLayout(header)

        # Body text & buttons based on state
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if state == "WaitingForUserConsent":
            desc = f"Wants to share: {', '.join(files) if files else text_desc or 'files'}"
            layout.addWidget(QLabel(desc))

            accept_btn = QPushButton("Accept")
            accept_btn.setStyleSheet("background-color: #10b981; color: white; border-radius: 8px; padding: 6px 16px;")
            accept_btn.clicked.connect(lambda: self.action_triggered.emit(self.msg_id, "AcceptTransfer"))

            decline_btn = QPushButton("Decline")
            decline_btn.setStyleSheet("background-color: #ef4444; color: white; border-radius: 8px; padding: 6px 16px;")
            decline_btn.clicked.connect(lambda: self.action_triggered.emit(self.msg_id, "RejectTransfer"))

            btn_layout.addWidget(accept_btn)
            btn_layout.addWidget(decline_btn)

        elif state in ["SentIntroduction", "SendingFiles", "ReceivingFiles"]:
            status_text = "Sending..." if state in ["SentIntroduction", "SendingFiles"] else "Receiving..."
            layout.addWidget(QLabel(f"{status_text}\n" + "\n".join(files)))

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setStyleSheet("background-color: #f59e0b; color: white; border-radius: 8px; padding: 6px 16px;")
            cancel_btn.clicked.connect(lambda: self.action_triggered.emit(self.msg_id, "CancelTransfer"))
            btn_layout.addWidget(cancel_btn)

        elif state == "Finished":
            msg = "Received:" if self.data.get("rtype") == "Inbound" else "Sent:"
            if files:
                msg += f"\n" + "\n".join(files)
            if destination:
                msg += f"\nSaved to: {destination}"
            if text_payload:
                msg += f"\n{text_payload}"
            layout.addWidget(QLabel(msg))

            if destination or text_payload:
                open_btn = QPushButton("Open")
                open_btn.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 8px; padding: 6px 16px;")
                open_btn.clicked.connect(lambda: self.open_path(destination or text_payload))
                btn_layout.addWidget(open_btn)

            clear_btn = QPushButton("Clear")
            clear_btn.setStyleSheet("background-color: #9ca3af; color: white; border-radius: 8px; padding: 6px 16px;")
            clear_btn.clicked.connect(lambda: self.clear_triggered.emit(self.msg_id))
            btn_layout.addWidget(clear_btn)

        elif state in ["Cancelled", "Rejected", "Disconnected"]:
            layout.addWidget(QLabel(f"Transfer {state.lower()}"))
            clear_btn = QPushButton("Clear")
            clear_btn.setStyleSheet("background-color: #9ca3af; color: white; border-radius: 8px; padding: 6px 16px;")
            clear_btn.clicked.connect(lambda: self.clear_triggered.emit(self.msg_id))
            btn_layout.addWidget(clear_btn)

        layout.addLayout(btn_layout)

    def open_path(self, path_str: str):
        if path_str:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path_str))


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsManager):
        super().__init__()
        self.settings = settings
        self.hostname = rqs_lib.get_hostname()
        self.outbound_files = []
        self.discovery_running = False
        self.requests_map = {}
        self.endpoints_map = {}

        self.setWindowTitle(f"RQuickShare - {self.hostname}")
        self.setMinimumSize(850, 550)
        self.setAcceptDrops(True)

        self.init_worker()
        self.init_ui()
        self.init_tray()

    def init_worker(self):
        visibility = self.settings.get("visibility", 1)
        port = self.settings.get("port")
        download_path = self.settings.get("download_path", str(Path.home() / "Downloads"))

        self.worker = RQSWorker(
            visibility=visibility,
            port=port,
            download_path=download_path,
            parent=self
        )
        self.worker.channel_message_received.connect(self.on_channel_message)
        self.worker.endpoint_info_received.connect(self.on_endpoint_info)
        self.worker.start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #d1fae5; padding: 16px;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setSpacing(16)

        # Hostname & status
        host_title = QLabel("Device Name")
        host_title.setStyleSheet("color: #065f46; font-size: 12px; font-weight: bold;")
        self.host_name_label = QLabel(self.hostname)
        host_font = QFont()
        host_font.setPointSize(14)
        host_font.setBold(True)
        self.host_name_label.setFont(host_font)
        self.host_name_label.setStyleSheet("color: #064e3b;")

        sidebar_layout.addWidget(host_title)
        sidebar_layout.addWidget(self.host_name_label)

        # Visibility toggle
        self.vis_btn = QPushButton()
        self.update_visibility_btn()
        self.vis_btn.clicked.connect(self.toggle_visibility)
        sidebar_layout.addWidget(self.vis_btn)

        # Discovery toggle
        self.disc_btn = QPushButton("Start Discovery")
        self.disc_btn.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 8px; border-radius: 8px;")
        self.disc_btn.clicked.connect(self.toggle_discovery)
        sidebar_layout.addWidget(self.disc_btn)

        # File payload selector
        select_file_btn = QPushButton("Select Files to Share")
        select_file_btn.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 10px; border-radius: 8px;")
        select_file_btn.clicked.connect(self.select_files)
        sidebar_layout.addWidget(select_file_btn)

        self.payload_status_label = QLabel("No files selected")
        self.payload_status_label.setWordWrap(True)
        self.payload_status_label.setStyleSheet("color: #047857; font-size: 11px;")
        sidebar_layout.addWidget(self.payload_status_label)

        sidebar_layout.addStretch()

        # Settings Button
        settings_btn = QPushButton("Settings")
        settings_btn.setStyleSheet("background-color: white; color: #065f46; font-weight: bold; padding: 8px; border-radius: 8px; border: 1px solid #6ee7b7;")
        settings_btn.clicked.connect(self.open_settings)
        sidebar_layout.addWidget(settings_btn)

        main_layout.addWidget(sidebar)

        # Main content area
        content_area = QWidget()
        content_area.setStyleSheet("background-color: white; border-top-left-radius: 24px; padding: 24px;")
        content_layout = QVBoxLayout(content_area)

        # Discovered Devices Section
        devices_header = QLabel("Nearby Devices")
        dh_font = QFont()
        dh_font.setPointSize(14)
        dh_font.setBold(True)
        devices_header.setFont(dh_font)
        content_layout.addWidget(devices_header)

        self.devices_list_widget = QListWidget()
        self.devices_list_widget.setMaximumHeight(140)
        self.devices_list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 8px;
                background-color: #f9fafb;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 8px;
                background-color: #ecfdf5;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: #a7f3d0;
            }
        """)
        self.devices_list_widget.itemClicked.connect(self.on_device_selected)
        content_layout.addWidget(self.devices_list_widget)

        # Transfers Section
        transfers_header = QLabel("Transfers")
        th_font = QFont()
        th_font.setPointSize(14)
        th_font.setBold(True)
        transfers_header.setFont(th_font)
        content_layout.addWidget(transfers_header)

        self.transfers_scroll = QScrollArea()
        self.transfers_scroll.setWidgetResizable(True)
        self.transfers_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.transfers_container = QWidget()
        self.transfers_layout = QVBoxLayout(self.transfers_container)
        self.transfers_layout.setContentsMargins(0, 0, 0, 0)
        self.transfers_layout.addStretch()

        self.transfers_scroll.setWidget(self.transfers_container)
        content_layout.addWidget(self.transfers_scroll, 1)

        main_layout.addWidget(content_area, 1)

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Use fallback standard icon or app icon
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show RQuickShare")
        show_action.triggered.connect(self.show_normal)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def update_visibility_btn(self):
        vis = self.settings.get("visibility", 1)
        if vis == 1:
            self.vis_btn.setText("Visibility: Everyone")
            self.vis_btn.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 8px; border-radius: 8px;")
        else:
            self.vis_btn.setText("Visibility: Hidden")
            self.vis_btn.setStyleSheet("background-color: #6b7280; color: white; font-weight: bold; padding: 8px; border-radius: 8px;")

    def toggle_visibility(self):
        current_vis = self.settings.get("visibility", 1)
        new_vis = 0 if current_vis == 1 else 1
        self.settings.set("visibility", new_vis)
        self.worker.change_visibility(new_vis)
        self.update_visibility_btn()

    def toggle_discovery(self):
        if self.discovery_running:
            self.worker.stop_discovery()
            self.discovery_running = False
            self.disc_btn.setText("Start Discovery")
            self.disc_btn.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 8px; border-radius: 8px;")
        else:
            self.worker.start_discovery()
            self.discovery_running = True
            self.disc_btn.setText("Stop Discovery")
            self.disc_btn.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; padding: 8px; border-radius: 8px;")

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files to Share")
        if files:
            self.outbound_files = files
            self.payload_status_label.setText(f"Ready to share {len(files)} file(s):\n" + ", ".join([Path(f).name for f in files]))
            if not self.discovery_running:
                self.toggle_discovery()

    def on_device_selected(self, item: QListWidgetItem):
        endpoint_id = item.data(Qt.UserRole)
        endpoint = self.endpoints_map.get(endpoint_id)
        if not endpoint:
            return

        if not self.outbound_files:
            QMessageBox.information(self, "No files selected", "Please click 'Select Files to Share' before sending.")
            return

        name = endpoint.get("name", "Unknown")
        addr = endpoint.get("addr", "")
        self.worker.send_payload(endpoint_id, name, addr, self.outbound_files)

    def on_channel_message(self, message: dict):
        msg_id = message.get("id")
        if not msg_id:
            return

        self.requests_map[msg_id] = message
        self.refresh_transfers_list()

        # Tray notification if user consent requested
        if message.get("state") == "WaitingForUserConsent":
            meta = message.get("meta") or {}
            source = meta.get("source") or {}
            name = source.get("name", "Unknown Device")
            self.tray_icon.showMessage(
                "RQuickShare Request",
                f"{name} wants to share files with you.",
                QSystemTrayIcon.Information,
                5000
            )

    def on_endpoint_info(self, endpoint: dict):
        ep_id = endpoint.get("id")
        present = endpoint.get("present", True)

        if not present:
            self.endpoints_map.pop(ep_id, None)
        else:
            self.endpoints_map[ep_id] = endpoint

        self.refresh_devices_list()

    def refresh_devices_list(self):
        self.devices_list_widget.clear()
        for ep_id, ep in self.endpoints_map.items():
            name = ep.get("name", "Unknown Device")
            addr = ep.get("addr", "")
            item = QListWidgetItem(f"📱 {name} ({addr})")
            item.setData(Qt.UserRole, ep_id)
            self.devices_list_widget.addItem(item)

    def refresh_transfers_list(self):
        # Clear existing card widgets
        for i in reversed(range(self.transfers_layout.count() - 1)):
            widget = self.transfers_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for msg_id, msg in self.requests_map.items():
            card = TransferCard(msg)
            card.action_triggered.connect(self.on_transfer_action)
            card.clear_triggered.connect(self.on_transfer_clear)
            self.transfers_layout.insertWidget(0, card)

    def on_transfer_action(self, target_id: str, action: str):
        self.worker.send_action(target_id, action)

    def on_transfer_clear(self, target_id: str):
        self.requests_map.pop(target_id, None)
        self.refresh_transfers_list()

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_updated.connect(self.apply_settings)
        dialog.exec()

    def apply_settings(self):
        self.update_visibility_btn()
        download_path = self.settings.get("download_path")
        if download_path:
            self.worker.set_download_path(download_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self.outbound_files = files
            self.payload_status_label.setText(f"Ready to share {len(files)} file(s):\n" + ", ".join([Path(f).name for f in files]))
            if not self.discovery_running:
                self.toggle_discovery()

    def closeEvent(self, event):
        if self.settings.get("realclose", False):
            self.quit_app()
        else:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "RQuickShare",
                "App minimized to system tray.",
                QSystemTrayIcon.Information,
                2000
            )

    def show_normal(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()

    def quit_app(self):
        self.worker.stop()
        QApplication.quit()
