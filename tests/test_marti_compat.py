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


def multipart_upload(field_name, filename, payload, boundary="taklite-test-boundary"):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        "Content-Type: application/zip\r\n"
        "\r\n"
    ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


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
        os.environ["TAKLITE_HTTPS_HOST_PORT"] = "18443"
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

    def test_missionupload_accepts_atak_plain_name_and_stores_zip_name(self):
        payload = datapackage_bytes("atak-maps")
        body, headers = multipart_upload("assetfile", "maps", payload)

        status, _, response = self.request(
            "POST",
            "/Marti/sync/missionupload?filename=maps&creatorUid=ANDROID-1",
            body,
            headers,
        )

        self.assertEqual(status, 200, response.decode("utf-8", "replace"))
        packages = self.service.list_packages()
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0]["Name"], "maps.zip")

    def test_upload_rejects_zip_entries_with_unsafe_paths(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("../evil.txt", "nope")

        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.service.validate_datapackage_upload("evil.zip", buffer.getvalue())

    def test_upload_rejects_excessive_zip_compression_ratio(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("large.txt", b"A" * (2 * 1024 * 1024))

        with self.assertRaisesRegex(ValueError, "compression ratio"):
            self.service.validate_datapackage_upload("compressed.zip", buffer.getvalue())

    def test_multipart_upload_accepts_common_file_field_names(self):
        for field_name in ("file", "upload", "content"):
            payload = datapackage_bytes(field_name)
            body, headers = multipart_upload(field_name, f"{field_name}.zip", payload)

            status, _, response = self.request(
                "POST",
                f"/Marti/sync/missionupload?filename={field_name}",
                body,
                headers,
            )

            self.assertEqual(status, 200, response.decode("utf-8", "replace"))

        packages = self.service.list_packages()
        self.assertEqual(
            {item["Name"] for item in packages},
            {"file.zip", "upload.zip", "content.zip"},
        )

    def test_sync_metadata_tool_updates_visibility(self):
        payload = datapackage_bytes("public-tool")
        status, _, response = self.request(
            "POST",
            "/Marti/sync/missionupload?hash=publichash&filename=public-map.zip&creatorUid=ANDROID-1",
            payload,
            {"Content-Type": "application/zip"},
        )
        self.assertEqual(status, 200, response.decode("utf-8", "replace"))

        status, _, response = self.request(
            "PUT",
            "/Marti/api/sync/metadata/publichash/tool",
            b"public",
            {"Content-Type": "text/plain"},
        )
        self.assertEqual(status, 200, response.decode("utf-8", "replace"))

        row = self.service.find_package("publichash")
        self.assertEqual(row["Tool"], "public")
        self.assertEqual(row["Visibility"], "public")
        self.assertTrue(self.service.package_visible_to_user(self.service.row_to_package(row), None, enforce=True))

    def test_marti_content_url_uses_configured_https_public_port(self):
        self.service.HTTPS_CERT.parent.mkdir(parents=True, exist_ok=True)
        self.service.HTTPS_CERT.write_text("cert", encoding="utf-8")
        self.service.HTTPS_KEY.write_text("key", encoding="utf-8")

        self.assertEqual(
            self.service.tak_marti_content_url("abc123"),
            "https://10.66.66.1:18443/Marti/sync/content?hash=abc123",
        )

    def test_legacy_p12_cert_downloads_are_disabled_by_default(self):
        cert_dir = pathlib.Path(self.tmpdir.name) / "certs"
        cert_dir.mkdir(exist_ok=True)
        (cert_dir / "taklite-truststore.p12").write_bytes(b"truststore")
        (cert_dir / "10.66.66.1.p12").write_bytes(b"truststore")

        for path in ("/certs/taklite-truststore.p12", "/certs/10.66.66.1.p12"):
            status, _, body = self.request("GET", path)

            self.assertEqual(status, 403, body.decode("utf-8", "replace"))

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
