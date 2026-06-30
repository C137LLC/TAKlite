import importlib.util
import os
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "docker" / "taklite" / "taklite_service.py"


def load_service(tmp, enabled=False, command="", request_dir="", settings_dir="", firewall_dir=""):
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
    os.environ["TAKLITE_SETTINGS_REQUEST_DIR"] = str(settings_dir) if settings_dir else ""
    os.environ["TAKLITE_FIREWALL_REQUEST_DIR"] = str(firewall_dir) if firewall_dir else ""
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

        self.assertEqual(status["current_tag"], "v0.2.15")
        self.assertTrue(status["gui_runner_enabled"])
        self.assertFalse(status["update_available"])
        self.assertTrue(status["check_error"])

    def test_admin_password_can_be_changed_with_current_password(self):
        service = load_service(self.tmp)
        service.create_admin("admin", "OriginalPass123!")
        token = service.create_session("admin")

        self.assertEqual(service.authenticate_admin("admin", "OriginalPass123!"), "admin")
        service.change_admin_password("admin", "OriginalPass123!", "NewPass12345!", token)

        self.assertEqual(service.authenticate_admin("admin", "OriginalPass123!"), "")
        self.assertEqual(service.authenticate_admin("admin", "NewPass12345!"), "admin")

    def test_admin_password_change_rejects_wrong_current_password(self):
        service = load_service(self.tmp)
        service.create_admin("admin", "OriginalPass123!")

        with self.assertRaises(PermissionError):
            service.change_admin_password("admin", "wrong-password", "NewPass12345!")

        self.assertEqual(service.authenticate_admin("admin", "OriginalPass123!"), "admin")

    def test_settings_runner_validates_and_queues_whitelisted_env(self):
        settings_dir = self.tmp / "settings"
        settings_dir.mkdir()
        service = load_service(self.tmp, settings_dir=settings_dir)

        result = service.queue_settings_update({"values": {
            "public_host": "10.66.66.1",
            "server_host": "10.66.66.1",
            "wg_dashboard_url": "http://10.66.66.1:10086",
            "max_upload_bytes": 10485760,
            "cot_host_port": 58087,
            "cot_tls_host_port": 8089,
            "http_host_port": 8080,
            "https_host_port": 8443,
            "access_control_enforce": True,
            "cot_tls_require_client_cert": "false",
            "allow_legacy_client_cert": False,
        }})

        self.assertTrue(result["ok"], result)
        request = (settings_dir / "request.json").read_text()
        self.assertIn('"TAKLITE_MAX_UPLOAD_BYTES": "10485760"', request)
        self.assertIn('"TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT": "false"', request)

    def test_settings_runner_rejects_bad_ports(self):
        settings_dir = self.tmp / "settings"
        settings_dir.mkdir()
        service = load_service(self.tmp, settings_dir=settings_dir)

        with self.assertRaises(ValueError):
            service.queue_settings_update({"values": {
                "public_host": "10.66.66.1",
                "server_host": "10.66.66.1",
                "wg_dashboard_url": "",
                "max_upload_bytes": 10485760,
                "cot_host_port": 70000,
                "cot_tls_host_port": 8089,
                "http_host_port": 8080,
                "https_host_port": 8443,
                "access_control_enforce": True,
                "cot_tls_require_client_cert": True,
                "allow_legacy_client_cert": False,
            }})

    def test_firewall_runner_blocks_wireguard_close_and_requires_ssh_confirmation(self):
        firewall_dir = self.tmp / "firewall"
        firewall_dir.mkdir()
        service = load_service(self.tmp, firewall_dir=firewall_dir)

        with self.assertRaises(ValueError) as wireguard_error:
            service.queue_firewall_update({"services": {"wireguard": "closed"}})
        self.assertIn("WireGuard", str(wireguard_error.exception))

        with self.assertRaises(ValueError) as ssh_error:
            service.queue_firewall_update({"services": {"ssh": "closed"}})
        self.assertIn("confirm SSH", str(ssh_error.exception))

    def test_firewall_runner_queues_managed_service_states(self):
        firewall_dir = self.tmp / "firewall"
        firewall_dir.mkdir()
        service = load_service(self.tmp, firewall_dir=firewall_dir)

        result = service.queue_firewall_update({"services": {
            "wireguard": "public",
            "ssh": "vpn",
            "taklite_admin": "vpn",
            "tak_https": "vpn",
            "cot_tcp": "vpn",
            "cot_tls": "vpn",
            "wg_dashboard": "vpn",
        }})

        self.assertTrue(result["ok"], result)
        self.assertTrue((firewall_dir / "request.json").exists())
        self.assertIn('"taklite_admin": "vpn"', (firewall_dir / "request.json").read_text())


if __name__ == "__main__":
    unittest.main()
