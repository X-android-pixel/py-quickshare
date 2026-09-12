import json
import os
import sys
from pathlib import Path


class SettingsManager:
    def __init__(self, filename: str = ".settings.json"):
        self.filename = filename
        self.filepath = self._get_settings_path()
        self.defaults = {
            "autostart": True,
            "realclose": False,
            "visibility": 1,  # 1 = Visible, 0 = Invisible
            "startminimized": False,
            "download_path": str(Path.home() / "Downloads"),
            "port": None,
            "debug_level": None,
        }
        self.data = {}
        self.load()

    def _get_settings_path(self) -> Path:
        home = Path.home()
        if sys.platform == "darwin":
            dir_path = home / "Library" / "Application Support" / "dev.mandre.rquickshare"
        else:
            dir_path = home / ".local" / "share" / "dev.mandre.rquickshare"
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / self.filename

    def load(self):
        self.data = dict(self.defaults)
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        self.data.update(content)
            except Exception as e:
                print(f"Error loading settings: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, self.defaults.get(key, default))

    def set(self, key: str, value):
        self.data[key] = value
        self.save()
