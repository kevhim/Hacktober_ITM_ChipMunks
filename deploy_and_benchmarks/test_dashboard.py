"""Unit and Integration Tests for Chaos-Harness Web Dashboard (Feature 1)."""

import json
import threading
import time
import unittest
import sys
import urllib.request
from pathlib import Path


# Add repository root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from deploy_and_benchmarks.dashboard import run_dashboard_server



class TestDashboardCore(unittest.TestCase):
    """Test suite for Feature 1: Core Dashboard Server & Target Explorer."""

    @classmethod
    def setUpClass(cls):
        cls.port = 8992
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(
            target=run_dashboard_server,
            kwargs={"host": "127.0.0.1", "port": cls.port, "force_mock": True},
            daemon=True,
        )
        cls.server_thread.start()
        time.sleep(0.5)

    def test_01_health_endpoint(self):
        """Verify /api/health returns HTTP 200 with model info."""
        with urllib.request.urlopen(f"{self.base_url}/api/health") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "healthy")
            self.assertIn("Gemma", data.get("provider_name", ""))
            self.assertTrue(data.get("force_mock"))

    def test_02_targets_endpoint(self):
        """Verify /api/targets returns the 5 benchmark targets."""
        with urllib.request.urlopen(f"{self.base_url}/api/targets") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data.get("count"), 5)
            self.assertEqual(len(data.get("targets", [])), 5)
            target_ids = [t["id"] for t in data["targets"]]
            self.assertIn("target-01-refund-bot", target_ids)

    def test_03_single_target_lookup(self):
        """Verify /api/targets/<id> returns specific target details."""
        with urllib.request.urlopen(f"{self.base_url}/api/targets/target-01-refund-bot") as response:
            self.assertEqual(response.status, 200)
            target = json.loads(response.read().decode("utf-8"))
            self.assertEqual(target.get("id"), "target-01-refund-bot")
            self.assertEqual(target.get("domain"), "e-commerce")
            self.assertIn("weak_system_prompt", target)

    def test_04_html_dashboard_served(self):
        """Verify / serves the glassmorphic Single Page App HTML."""
        with urllib.request.urlopen(f"{self.base_url}/") as response:
            self.assertEqual(response.status, 200)
            content = response.read().decode("utf-8")
            self.assertIn("<title>Chaos-Harness", content)
            self.assertIn("targetSelect", content)
            self.assertIn("promptTextarea", content)


if __name__ == "__main__":
    unittest.main()
