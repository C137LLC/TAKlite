import importlib.util
import pathlib
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "docker" / "taklite" / "taklite_service.py"


spec = importlib.util.spec_from_file_location("taklite_service", SERVICE_PATH)
taklite_service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(taklite_service)


class BulkUserPlanningTests(unittest.TestCase):
    def test_builds_numbered_usernames_from_prefix_and_count(self):
        plan = taklite_service.build_bulk_usernames("user", 3)

        self.assertEqual(plan, ["user1", "user2", "user3"])

    def test_rejects_invalid_prefix(self):
        with self.assertRaisesRegex(ValueError, "bulk username prefix"):
            taklite_service.build_bulk_usernames("bad name", 2)

    def test_rejects_out_of_range_count(self):
        with self.assertRaisesRegex(ValueError, "between 1 and"):
            taklite_service.build_bulk_usernames("user", 0)

    def test_bulk_create_uses_atakatak_as_shared_password_for_batch(self):
        created = []

        def fake_create(username, password, display_name, description, allow_redownload):
            created.append((username, password, display_name, description, allow_redownload))
            return {
                "id": len(created),
                "username": username,
                "cert_profile_id": len(created) + 10,
                "portal_path": f"/connect/?u={username}",
                "connect_string": "10.66.66.1:8089:ssl",
            }

        with mock.patch.object(taklite_service, "ensure_bulk_users_available"), \
             mock.patch.object(taklite_service, "create_portal_user", side_effect=fake_create):
            result = taklite_service.create_bulk_portal_users("team", 3, base_url="http://10.66.66.1:8080")

        self.assertEqual(result["count"], 3)
        self.assertEqual(result["shared_password"], "atakatak")
        self.assertEqual({item["password"] for item in result["items"]}, {"atakatak"})
        self.assertEqual([row[0] for row in created], ["team1", "team2", "team3"])


if __name__ == "__main__":
    unittest.main()
