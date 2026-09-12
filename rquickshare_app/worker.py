import json
import time
from PySide6.QtCore import QThread, Signal
import rqs_lib


class RQSWorker(QThread):
    channel_message_received = Signal(dict)
    endpoint_info_received = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, visibility: int = 1, port: int = None, download_path: str = None, parent=None):
        super().__init__(parent)
        self.visibility = visibility
        self.port = port
        self.download_path = download_path
        self._running = True
        self.rqs = None

    def run(self):
        try:
            self.rqs = rqs_lib.PyRQS(
                visibility=self.visibility,
                port_number=self.port,
                download_path=self.download_path
            )
            self.rqs.start()
        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize RQS: {e}")
            return

        while self._running:
            try:
                raw_messages = self.rqs.poll_messages()
                for msg_str in raw_messages:
                    data = json.loads(msg_str)
                    event = data.get("event")
                    payload = data.get("payload", {})
                    if event == "rs2js_channelmessage":
                        self.channel_message_received.emit(payload)
                    elif event == "rs2js_endpointinfo":
                        self.endpoint_info_received.emit(payload)
            except Exception as e:
                print(f"Error polling RQS messages: {e}")

            time.sleep(0.1)

    def stop(self):
        self._running = False
        if self.rqs:
            try:
                self.rqs.stop()
            except Exception as e:
                print(f"Error stopping RQS: {e}")

    def start_discovery(self):
        if self.rqs:
            self.rqs.start_discovery()

    def stop_discovery(self):
        if self.rqs:
            self.rqs.stop_discovery()

    def change_visibility(self, visibility: int):
        self.visibility = visibility
        if self.rqs:
            self.rqs.change_visibility(visibility)

    def set_download_path(self, download_path: str):
        self.download_path = download_path
        if self.rqs:
            self.rqs.set_download_path(download_path)

    def send_payload(self, target_id: str, name: str, addr: str, files: list):
        if self.rqs:
            self.rqs.send_payload(target_id, name, addr, files)

    def send_action(self, target_id: str, action: str):
        if self.rqs:
            self.rqs.send_action(target_id, action)
