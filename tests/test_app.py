import os
import unittest
from pathlib import Path
from rquickshare_app.settings import SettingsManager
import rqs_lib


class TestSettingsManager(unittest.TestCase):
    def test_settings_load_and_set(self):
        sm = SettingsManager(filename=".test_settings.json")
        sm.set("visibility", 0)
        self.assertEqual(sm.get("visibility"), 0)

        # Cleanup test settings file
        if sm.filepath.exists():
            os.remove(sm.filepath)

    def test_pyrqs_instantiation(self):
        hostname = rqs_lib.get_hostname()
        self.assertTrue(isinstance(hostname, str))
        self.assertGreater(len(hostname), 0)

        rqs = rqs_lib.PyRQS(visibility=1, port_number=None, download_path=None)
        self.assertIsNotNone(rqs)


if __name__ == "__main__":
    unittest.main()
