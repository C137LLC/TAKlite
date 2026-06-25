import http.client
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import threading
import unittest
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "docker" / "taklite" / "taklite_service.py"


def datapackage_bytes(label="default"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.xml", "<MissionPackageManifest/>")
        zf.writestr("payload.txt", label)
    return buffer.getvalue()


class MartiCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(self.tmpdir.name)
        os.environ["TAKLITE_DB"] = str(tmp / "taklite.sqlite3")
        os.environ["TAKLITE_PACKAGE_DIR"] = str(tmp / "packages")
        os.environ["TAKLITE_HTTPS_CERT"] = str(tmp / "certs" / "taklite.crt")
        os.environ["TAKLITE_HTTPS_KEY"] = str(tmp / "certs" / "taklite.key")
        os.environ["TAKLITE_CLIENT_CA"] = str(tmp / "certs" / "taklite-ca.crt")
        os.environ["TAKLITE_CERT_PASSWORD"] = "atakatak"
        os.environ["TAKLITE_ACCESS_CONTROL_ENFORCE"] = "false"
        spec = importlib.util.spec_from_file_location("taklite_service_marti", SERVICE_PATH)
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.service.init_db()
        self.server = self.service.ThreadingHTTPServer(("127.0.0.1", 0), self.service.HttpHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmpdir.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read()
            return response.status, dict(response.getheaders()), data
        finally:
            conn.close()

    def test_head_sync_content_reports_existing_package_without_body(self):
        data = datapackage_bytes()
        url = self.service.upsert_package("abc123", "alpha.dp.zip", "ANDROID-1", data, "http://127.0.0.1")
        self.assertIn("abc123", url)

        status, headers, body = self.request("HEAD", "/Marti/sync/content?hash=abc123")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Length"], str(len(data)))
        self.assertEqual(body, b"")

    def test_alternate_upload_paths_store_datapackages(self):
        for path in (
            "/Marti/sync/upload?filename=upload.dp.zip&creatorUid=ANDROID-1",
            "/Marti/sync/content?filename=put.dp.zip&creatorUid=ANDROID-2",
        ):
            method = "PUT" if "put" in path else "POST"
            payload = datapackage_bytes(path)
            status, _, body = self.request(method, path, payload, {"Content-Type": "application/zip"})

            self.assertEqual(status, 200, body.decode("utf-8", "replace"))
            self.assertIn(b"/Marti/sync/content?hash=", body)

        packages = self.service.list_packages()
        self.assertEqual({item["Name"] for item in packages}, {"upload.dp.zip", "put.dp.zip"})

    def test_groups_all_returns_named_access_groups(self):
        self.service.create_access_group("Alpha", color="#55cc88")
        self.service.create_access_group("Bravo", color="#1188ff")

        status, _, body = self.request("GET", "/Marti/api/groups/all")

        self.assertEqual(status, 200)
        result = json.loads(body.decode("utf-8"))
        self.assertEqual(result["version"], 3)
        self.assertEqual(result["type"], "GroupList")
        self.assertEqual([item["name"] for item in result["data"]], ["Alpha", "Bravo"])

    def test_client_endpoints_use_compatibility_shape(self):
        class FakeRelay:
            def snapshot(self):
                return [{
                    "uid": "ANDROID-1",
                    "callsign": "Alpha One",
                    "ip": "10.66.66.3",
                    "port": 45500,
                    "transport": "tls",
                    "username": "alpha1",
                    "connected_at": "2026-06-25T15:00:00Z",
                    "last_seen": "2026-06-25T15:00:12Z",
                }]

        self.service.RELAY = FakeRelay()

        status, _, body = self.request("GET", "/Marti/api/clientEndPoints")

        self.assertEqual(status, 200)
        result = json.loads(body.decode("utf-8"))
        self.assertEqual(result["version"], 3)
        self.assertEqual(result["type"], "ClientEndpointList")
        self.assertEqual(result["data"][0]["uid"], "ANDROID-1")
        self.assertEqual(result["data"][0]["callsign"], "Alpha One")
        self.assertEqual(result["data"][0]["address"], "10.66.66.3")
        self.assertEqual(result["data"][0]["lastEventTime"], "2026-06-25T15:00:12Z")

    def test_mission_compatibility_routes_return_empty_lists(self):
        for path in (
            "/Marti/api/missions/training/changes",
            "/Marti/api/missions/training/contents",
            "/Marti/api/missions/invitations",
        ):
            status, _, body = self.request("GET", path)
            result = json.loads(body.decode("utf-8"))

            self.assertEqual(status, 200)
            self.assertEqual(result["version"], 3)
            self.assertEqual(result["data"], [])


if __name__ == "__main__":
    unittest.main()
