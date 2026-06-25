import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleasePackagingTests(unittest.TestCase):
    def test_dockerfile_makes_service_readable_by_non_root_user(self):
        dockerfile = (ROOT / "docker" / "taklite" / "Dockerfile").read_text()

        self.assertIn("COPY --chmod=0644 docker/taklite/taklite_service.py /app/taklite_service.py", dockerfile)

    def test_release_defaults_enable_policy_ready_secure_mode(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        env_example = (ROOT / ".env.example").read_text()
        installer = (ROOT / "install.sh").read_text()

        self.assertIn("TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT: \"${TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT:-true}\"", compose)
        self.assertIn("TAKLITE_ALLOW_LEGACY_CLIENT_CERT: \"${TAKLITE_ALLOW_LEGACY_CLIENT_CERT:-false}\"", compose)
        self.assertIn("TAKLITE_ACCESS_CONTROL_ENFORCE: \"${TAKLITE_ACCESS_CONTROL_ENFORCE:-true}\"", compose)
        self.assertIn("TAKLITE_COT_TLS_REQUIRE_CLIENT_CERT=true", env_example)
        self.assertIn("TAKLITE_ALLOW_LEGACY_CLIENT_CERT=false", env_example)
        self.assertIn("TAKLITE_ACCESS_CONTROL_ENFORCE=true", env_example)
        self.assertIn('prompt_default "Enable secure mode: require TLS cert identity and enforce groups" "yes"', installer)


if __name__ == "__main__":
    unittest.main()
