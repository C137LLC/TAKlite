import importlib.util
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "docker" / "taklite" / "taklite_service.py"


def load_service(tmp, enabled=False, command=""):
    os.environ["TAKLITE_DB"] = str(tmp / "taklite.sqlite3")
    os.environ["TAKLITE_PACKAGE_DIR"] = str(tmp / "packages")
    os.environ["TAKLITE_HTTPS_CERT"] = str(tmp / "certs" / "taklite.crt")
    os.environ["TAKLITE_HTTPS_KEY"] = str(tmp / "certs" / "taklite.key")
    os.environ["TAKLITE_CLIENT_CA"] = str(tmp / "certs" / "taklite-ca.crt")
    os.environ["TAKLITE_CERT_PASSWORD"] = "atakatak"
    os.environ["TAKLITE_GUI_UPDATE_ENABLED"] = "true" if enabled else "false"
    os.environ["TAKLITE_GUI_UPDATE_COMMAND"] = command
    os.environ["TAKLITE_GUI_UPDATE_WORKDIR"] = str(tmp)
    os.environ["TAKLITE_GUI_UPDATE_TIMEOUT_SECONDS"] = "5"
    spec = importlib.util.spec_from_file_location(f"taklite_service_update_{enabled}", SERVICE_PATH)
    service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service)
    service.init_db()
    return service


class GuiUpdateRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_gui_update_runner_is_disabled_by_default(self):
        marker = self.tmp / "should-not-exist"
        service = load_service(self.tmp, enabled=False, command=f"/bin/sh -c 'touch {marker}'")

        status = service.gui_update_status()
        result = service.run_gui_update("RUN_UPDATE")

        self.assertFalse(status["enabled"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "GUI update runner is disabled")
        self.assertFalse(marker.exists())

    def test_gui_update_runner_requires_confirmation_and_uses_configured_command(self):
        marker = self.tmp / "updated.txt"
        command = f"/bin/sh -c 'echo updated > {marker}'"
        service = load_service(self.tmp, enabled=True, command=command)

        refused = service.run_gui_update("wrong")
        result = service.run_gui_update("RUN_UPDATE")

        self.assertFalse(refused["ok"])
        self.assertIn("confirmation", refused["error"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(marker.read_text().strip(), "updated")


if __name__ == "__main__":
    unittest.main()
