import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleasePackagingTests(unittest.TestCase):
    def test_dockerfile_makes_service_readable_by_non_root_user(self):
        dockerfile = (ROOT / "docker" / "taklite" / "Dockerfile").read_text()

        self.assertIn("COPY --chmod=0644 docker/taklite/taklite_service.py /app/taklite_service.py", dockerfile)


if __name__ == "__main__":
    unittest.main()
