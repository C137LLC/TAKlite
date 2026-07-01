import importlib.util
import json
import os
import pathlib
import tempfile
import threading
import urllib.request
import unittest
import zipfile
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "docker" / "taklite" / "taklite_service.py"


class AccessControlTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(self.tmpdir.name)
        os.environ["TAKLITE_DB"] = str(tmp / "taklite.sqlite3")
        os.environ["TAKLITE_PACKAGE_DIR"] = str(tmp / "packages")
        os.environ["TAKLITE_HTTPS_CERT"] = str(tmp / "certs" / "taklite.crt")
        os.environ["TAKLITE_HTTPS_KEY"] = str(tmp / "certs" / "taklite.key")
        os.environ["TAKLITE_CLIENT_CA"] = str(tmp / "certs" / "taklite-ca.crt")
        os.environ["TAKLITE_CERT_PASSWORD"] = "atakatak"
        spec = importlib.util.spec_from_file_location("taklite_service_policy", SERVICE_PATH)
        self.service = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.service)
        self.service.init_db()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_roles_groups_and_links_are_name_agnostic(self):
        observer = self.service.create_access_role("Observer", can_see_all=True, can_send_all=True)
        participant = self.service.create_access_role("Participant", can_see_own_groups=True, can_send_own_groups=True)
        hidden = self.service.create_access_role("Beacon", can_see_own_groups=False, can_send_own_groups=False)
        alpha = self.service.create_access_group("Alpha")
        bravo = self.service.create_access_group("Bravo")
        beacon = self.service.create_access_group("Beacon")

        lead = self.service.create_policy_subject("lead", role_id=observer["id"], group_ids=[alpha["id"]])
        alpha_one = self.service.create_policy_subject("alpha-one", role_id=participant["id"], group_ids=[alpha["id"]])
        alpha_two = self.service.create_policy_subject("alpha-two", role_id=participant["id"], group_ids=[alpha["id"]])
        bravo_one = self.service.create_policy_subject("bravo-one", role_id=participant["id"], group_ids=[bravo["id"]])
        beacon_one = self.service.create_policy_subject("beacon-one", role_id=hidden["id"], group_ids=[beacon["id"]])

        self.assertTrue(self.service.can_subject_see(lead["id"], alpha_one["id"]))
        self.assertTrue(self.service.can_subject_see(lead["id"], bravo_one["id"]))
        self.assertTrue(self.service.can_subject_see(lead["id"], beacon_one["id"]))

        self.assertTrue(self.service.can_subject_see(alpha_one["id"], alpha_two["id"]))
        self.assertFalse(self.service.can_subject_see(alpha_one["id"], bravo_one["id"]))
        self.assertFalse(self.service.can_subject_see(alpha_one["id"], beacon_one["id"]))
        self.assertFalse(self.service.can_subject_see(beacon_one["id"], alpha_one["id"]))

        self.service.set_policy_link(alpha["id"], beacon["id"], can_see=True, can_send=False)
        self.assertTrue(self.service.can_subject_see(alpha_one["id"], beacon_one["id"]))
        self.assertFalse(self.service.can_subject_send(alpha_one["id"], beacon_one["id"]))

    def test_unassigned_users_are_open_when_no_policy_is_assigned(self):
        alpha_one = self.service.create_policy_subject("alpha-one")
        bravo_one = self.service.create_policy_subject("bravo-one")

        self.assertFalse(self.service.access_policy_active())
        self.assertTrue(self.service.can_subject_see(alpha_one["id"], bravo_one["id"]))
        self.assertTrue(self.service.can_subject_send(alpha_one["id"], bravo_one["id"]))
        self.assertTrue(self.service.can_subject_see(bravo_one["id"], alpha_one["id"]))
        self.assertTrue(self.service.cot_delivery_allowed(alpha_one["id"], bravo_one["id"], enforce=True))

        package = {"CreatorUserId": alpha_one["id"], "Tool": "private"}
        self.assertTrue(self.service.package_visible_to_user(package, bravo_one["id"], enforce=True))

        preview = self.service.access_preview(alpha_one["id"])
        self.assertFalse(preview["policy_active"])
        self.assertTrue(preview["open_default"])
        self.assertEqual({item["username"] for item in preview["can_see"]}, {"alpha-one", "bravo-one"})

    def test_access_policy_becomes_active_after_membership_assignment(self):
        participant = self.service.create_access_role("Participant", can_see_own_groups=True, can_send_own_groups=True)
        alpha = self.service.create_access_group("Alpha")
        alpha_one = self.service.create_policy_subject("alpha-one", role_id=participant["id"], group_ids=[alpha["id"]])
        bravo_one = self.service.create_policy_subject("bravo-one")

        self.assertTrue(self.service.access_policy_active())
        self.assertFalse(self.service.can_subject_see(alpha_one["id"], bravo_one["id"]))
        self.assertFalse(self.service.can_subject_send(alpha_one["id"], bravo_one["id"]))

        package = {"CreatorUserId": alpha_one["id"], "Tool": "private"}
        self.assertFalse(self.service.package_visible_to_user(package, bravo_one["id"], enforce=True))

    def test_admin_api_creates_roles_and_groups(self):
        self.service.create_admin("admin", "password1234")
        session = self.service.create_session("admin")
        server = self.service.ThreadingHTTPServer(("127.0.0.1", 0), self.service.HttpHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"

        def request_json(path, payload=None):
            body = None if payload is None else json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                f"{base_url}{path}",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Session-Token": session,
                },
                method="GET" if payload is None else "POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            role = request_json("/api/access-roles/create", {"name": "Range Lead", "can_see_all": True})
            group = request_json("/api/access-groups/create", {"name": "Blue Team", "color": "#64c18c"})
            summary = request_json("/api/access-control")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(role["name"], "Range Lead")
        self.assertTrue(role["can_see_all"])
        self.assertEqual(group["name"], "Blue Team")
        self.assertEqual([item["name"] for item in summary["roles"]], ["Range Lead"])
        self.assertEqual([item["name"] for item in summary["groups"]], ["Blue Team"])

    def test_tls_identity_maps_to_portal_user_and_filters_cot_delivery(self):
        participant = self.service.create_access_role("Participant", can_see_own_groups=True, can_send_own_groups=True)
        observer = self.service.create_access_role("Observer", can_see_all=True, can_send_all=True)
        alpha = self.service.create_access_group("Alpha")
        bravo = self.service.create_access_group("Bravo")

        lead = self.service.create_policy_subject("lead", role_id=observer["id"], group_ids=[alpha["id"]])
        alpha_one = self.service.create_policy_subject("alpha-one", role_id=participant["id"], group_ids=[alpha["id"]])
        alpha_two = self.service.create_policy_subject("alpha-two", role_id=participant["id"], group_ids=[alpha["id"]])
        bravo_one = self.service.create_policy_subject("bravo-one", role_id=participant["id"], group_ids=[bravo["id"]])

        self.assertEqual(self.service.client_identity_for_cert("alpha-one")["user_id"], alpha_one["id"])
        self.assertTrue(self.service.cot_delivery_allowed(alpha_one["id"], alpha_two["id"], enforce=True))
        self.assertFalse(self.service.cot_delivery_allowed(alpha_one["id"], bravo_one["id"], enforce=True))
        self.assertTrue(self.service.cot_delivery_allowed(lead["id"], bravo_one["id"], enforce=True))
        self.assertFalse(self.service.cot_delivery_allowed(None, alpha_one["id"], enforce=True))
        self.assertTrue(self.service.cot_delivery_allowed(None, alpha_one["id"], enforce=False))

    def test_individual_user_access_can_replace_and_clear_assignments(self):
        participant = self.service.create_access_role("Participant", can_see_own_groups=True, can_send_own_groups=True)
        alpha = self.service.create_access_group("Alpha")
        bravo = self.service.create_access_group("Bravo")
        user = self.service.create_policy_subject("alpha-one", role_id=participant["id"], group_ids=[alpha["id"]])

        updated = self.service.set_user_access(user["id"], role_id=participant["id"], group_ids=[bravo["id"]])
        self.assertEqual(updated["role_id"], participant["id"])
        self.assertEqual(updated["group_ids"], [bravo["id"]])

        cleared = self.service.set_user_access(user["id"], role_id=None, group_ids=[])
        self.assertIsNone(cleared["role_id"])
        self.assertEqual(cleared["group_ids"], [])

    def test_datapackage_visibility_follows_creator_groups(self):
        participant = self.service.create_access_role("Participant", can_see_own_groups=True, can_send_own_groups=True)
        observer = self.service.create_access_role("Observer", can_see_all=True, can_send_all=True)
        alpha = self.service.create_access_group("Alpha")
        bravo = self.service.create_access_group("Bravo")

        lead = self.service.create_policy_subject("lead", role_id=observer["id"], group_ids=[alpha["id"]])
        alpha_one = self.service.create_policy_subject("alpha-one", role_id=participant["id"], group_ids=[alpha["id"]])
        alpha_two = self.service.create_policy_subject("alpha-two", role_id=participant["id"], group_ids=[alpha["id"]])
        bravo_one = self.service.create_policy_subject("bravo-one", role_id=participant["id"], group_ids=[bravo["id"]])

        package = {"CreatorUserId": alpha_one["id"], "Tool": "private"}
        self.assertTrue(self.service.package_visible_to_user(package, alpha_one["id"], enforce=True))
        self.assertTrue(self.service.package_visible_to_user(package, alpha_two["id"], enforce=True))
        self.assertTrue(self.service.package_visible_to_user(package, lead["id"], enforce=True))
        self.assertFalse(self.service.package_visible_to_user(package, bravo_one["id"], enforce=True))
        self.assertTrue(self.service.package_visible_to_user(package, None, enforce=False))

    def test_public_tool_datapackage_is_visible_without_identity(self):
        package = {"CreatorUserId": None, "Visibility": "private", "Tool": "public"}

        self.assertTrue(self.service.package_visible_to_user(package, None, enforce=True))

    def test_access_preview_reports_visible_and_seen_by_users(self):
        admin = self.service.create_access_role("Admin", can_see_all=True, can_send_all=True)
        student = self.service.create_access_role("Student", can_see_own_groups=True, can_send_own_groups=True)
        hidden = self.service.create_access_role("Hidden", can_see_own_groups=False, can_send_own_groups=False)
        alpha = self.service.create_access_group("Alpha")
        rabbit = self.service.create_access_group("Rabbit")

        lead = self.service.create_policy_subject("lead", role_id=admin["id"], group_ids=[])
        alpha_one = self.service.create_policy_subject("alpha-one", role_id=student["id"], group_ids=[alpha["id"]])
        alpha_two = self.service.create_policy_subject("alpha-two", role_id=student["id"], group_ids=[alpha["id"]])
        rabbit_one = self.service.create_policy_subject("rabbit-one", role_id=hidden["id"], group_ids=[rabbit["id"]])

        alpha_preview = self.service.access_preview(alpha_one["id"])
        rabbit_preview = self.service.access_preview(rabbit_one["id"])

        self.assertEqual({item["username"] for item in alpha_preview["can_see"]}, {"alpha-one", "alpha-two"})
        self.assertNotIn("lead", {item["username"] for item in alpha_preview["can_see"]})
        self.assertNotIn("rabbit-one", {item["username"] for item in alpha_preview["can_see"]})
        self.assertEqual({item["username"] for item in rabbit_preview["can_see"]}, {"rabbit-one"})
        self.assertIn("lead", {item["username"] for item in rabbit_preview["seen_by"]})

    def test_runtime_health_reports_database_and_storage(self):
        health = self.service.runtime_health()

        self.assertTrue(health["database"]["ok"])
        self.assertGreaterEqual(health["storage"]["package_bytes"], 0)
        self.assertIn("access_enforcement", health["security"])

    def test_cot_send_timeout_is_scoped_to_outbound_writes(self):
        class FakeRequest:
            def __init__(self):
                self.timeout = None
                self.timeouts = []
                self.sent = []

            def gettimeout(self):
                return self.timeout

            def settimeout(self, value):
                self.timeouts.append(value)
                self.timeout = value

            def sendall(self, data):
                self.sent.append(data)

        class FakeHandler:
            def __init__(self):
                self.request = FakeRequest()
                self.send_lock = threading.Lock()

        relay = self.service.CotRelay()
        handler = FakeHandler()

        self.assertTrue(relay.send_to(handler, b"<event></event>"))
        self.assertEqual(handler.request.sent, [b"<event></event>"])
        self.assertEqual(handler.request.timeouts, [self.service.SOCKET_SEND_TIMEOUT_SECONDS, None])
        self.assertIsNone(handler.request.gettimeout())

    def test_connection_datapackage_uses_connection_scoped_cert_preferences(self):
        cert_dir = pathlib.Path(self.tmpdir.name) / "certs"
        cert_dir.mkdir(exist_ok=True)
        (cert_dir / "taklite-ca.crt").write_text("ca", encoding="utf-8")
        (cert_dir / "taklite-ca.key").write_text("key", encoding="utf-8")
        truststore = cert_dir / "taklite-truststore.p12"
        truststore.write_bytes(b"truststore")
        openssl_calls = []

        def fake_openssl(args):
            openssl_calls.append(args)
            if "-out" in args:
                out_path = pathlib.Path(args[args.index("-out") + 1])
                out_path.write_bytes(b"generated")

        with mock.patch.object(self.service, "ensure_truststore_file", return_value=truststore), \
             mock.patch.object(self.service, "run_openssl", side_effect=fake_openssl):
            profile = self.service.create_cert_profile("alpha-phone", "test")

        package = cert_dir / profile["datapackage_file"]
        with zipfile.ZipFile(package) as zf:
            names = zf.namelist()

        self.assertEqual(names.count("MANIFEST/manifest.xml"), 1)
        self.assertEqual(names.count("certs/server.pref"), 1)
        self.assertEqual(names.count("certs/taklite-server.pref"), 0)
        self.assertEqual(names.count("certs/10.66.66.1.p12"), 1)
        self.assertEqual(names.count("certs/alpha-phone.p12"), 1)
        self.assertNotIn("manifest.xml", names)
        self.assertNotIn("server.pref", names)
        self.assertNotIn("taklite-server.pref", names)
        self.assertEqual(len(names), len(set(names)))
        with zipfile.ZipFile(package) as zf:
            server_pref = zf.read("certs/server.pref").decode("utf-8")
            manifest = zf.read("MANIFEST/manifest.xml").decode("utf-8")
        self.assertIn('<entry key="description0" class="class java.lang.String">TAKlite alpha-phone</entry>', server_pref)
        self.assertIn('<entry key="caLocation0" class="class java.lang.String">cert/10.66.66.1.p12</entry>', server_pref)
        self.assertIn('<entry key="certificateLocation0" class="class java.lang.String">cert/alpha-phone.p12</entry>', server_pref)
        self.assertIn('<entry key="caLocation" class="class java.lang.String">cert/10.66.66.1.p12</entry>', server_pref)
        self.assertIn('<entry key="certificateLocation" class="class java.lang.String">cert/alpha-phone.p12</entry>', server_pref)
        self.assertIn('<entry key="caPassword" class="class java.lang.String">atakatak</entry>', server_pref)
        self.assertIn('<entry key="clientPassword" class="class java.lang.String">atakatak</entry>', server_pref)
        self.assertIn('<entry key="apiSecureServerPort" class="class java.lang.String">8443</entry>', server_pref)
        self.assertIn('<entry key="apiUnsecureServerPort" class="class java.lang.String">8080</entry>', server_pref)
        self.assertIn('<Parameter name="onReceiveImport" value="true"/>', manifest)
        self.assertIn('<Content ignore="false" zipEntry="certs/server.pref"/>', manifest)
        self.assertIn('<Content ignore="false" zipEntry="certs/10.66.66.1.p12"/>', manifest)
        self.assertIn('<Content ignore="false" zipEntry="certs/alpha-phone.p12"/>', manifest)
        pkcs12_calls = [call for call in openssl_calls if call[:2] == ["pkcs12", "-export"]]
        self.assertEqual(len(pkcs12_calls), 1)
        self.assertIn("-certpbe", pkcs12_calls[0])
        self.assertIn("PBE-SHA1-3DES", pkcs12_calls[0])
        self.assertIn("-keypbe", pkcs12_calls[0])
        self.assertIn("-macalg", pkcs12_calls[0])
        self.assertIn("sha1", pkcs12_calls[0])

    def test_truststore_file_uses_stable_non_server_cert_name(self):
        cert_dir = pathlib.Path(self.tmpdir.name) / "certs"
        cert_dir.mkdir(exist_ok=True)
        (cert_dir / "taklite-ca.crt").write_text("ca", encoding="utf-8")
        (cert_dir / "taklite-ca.key").write_text("key", encoding="utf-8")
        openssl_calls = []

        def fake_openssl(args):
            openssl_calls.append(args)
            out_path = pathlib.Path(args[args.index("-out") + 1])
            out_path.write_bytes(b"truststore")

        with mock.patch.object(self.service, "run_openssl", side_effect=fake_openssl):
            truststore = self.service.ensure_truststore_file()

        self.assertEqual(truststore.name, "taklite-truststore.p12")
        self.assertTrue(truststore.exists())
        pkcs12_calls = [call for call in openssl_calls if call[:2] == ["pkcs12", "-export"]]
        self.assertEqual(len(pkcs12_calls), 1)
        self.assertIn("-certfile", pkcs12_calls[0])
        self.assertIn(str(cert_dir / "taklite-ca.crt"), pkcs12_calls[0])
        self.assertIn("-inkey", pkcs12_calls[0])
        self.assertIn("-certpbe", pkcs12_calls[0])
        self.assertIn("PBE-SHA1-3DES", pkcs12_calls[0])
        self.assertIn("-keypbe", pkcs12_calls[0])
        self.assertIn("-macalg", pkcs12_calls[0])
        self.assertIn("sha1", pkcs12_calls[0])


if __name__ == "__main__":
    unittest.main()
