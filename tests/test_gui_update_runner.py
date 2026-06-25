import importlib.util
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "docker" / "taklite" / "taklite_service.py"


def load_service(tmp, enabled=False, command="", request_dir=""):
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
    os.environ["TAKLITE_GUI_UPDATE_REQUEST_DIR"] = str(request_dir) if request_dir else ""
    spec = importlib.util.spec_from_file_location(f"taklite_service_update_{enabled}_{bool(request_dir)}", SERVICE_PATH)
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

    def test_gui_update_runner_can_queue_host_request_file(self):
        request_dir = self.tmp / "gui-update"
        request_dir.mkdir()
        service = load_service(self.tmp, enabled=True, request_dir=request_dir)

        status = service.gui_update_status()
        result = service.run_gui_update("RUN_UPDATE", "v0.2.99")

        self.assertEqual(status["runner_mode"], "request")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["queued"])
        self.assertTrue((request_dir / "request.json").exists())
        self.assertIn("v0.2.99", (request_dir / "request.json").read_text())

    def test_version_helpers_parse_release_tags(self):
        service = load_service(self.tmp)

        self.assertEqual(service.version_tuple("TAKlite 0.2.13"), (0, 2, 13))
        self.assertEqual(service.version_tuple("v1.4.2"), (1, 4, 2))
        self.assertEqual(service.version_tag("TAKlite 0.2.13"), "v0.2.13")

    def test_update_status_reports_check_failure_without_running_update(self):
        service = load_service(self.tmp, enabled=True, command="/bin/true")
        service.LATEST_RELEASE_API_URL = "http://127.0.0.1:1/nope"

        status = service.latest_release_status(refresh=True)

        self.assertEqual(status["current_tag"], "v0.2.13")
        self.assertTrue(status["gui_runner_enabled"])
        self.assertFalse(status["update_available"])
        self.assertTrue(status["check_error"])


if __name__ == "__main__":
    unittest.main()
