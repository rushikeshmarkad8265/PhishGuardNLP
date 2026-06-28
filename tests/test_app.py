import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
from app import analyze, create_app


class RiskAnalysisTests(unittest.TestCase):
    def test_neutral_message_is_low_risk(self):
        result = analyze(
            "Course update",
            "The next lecture will take place in room 204.",
        )

        self.assertEqual(result["risk_tag"], "Low")
        self.assertLess(result["risk_score"], 35)

    def test_reinforced_emotional_pressure_is_high_risk(self):
        result = analyze(
            "Need help now",
            "I am in serious trouble and need money urgently. "
            "Please do not tell anyone. Help me now.",
        )

        self.assertEqual(result["risk_tag"], "High")
        categories = {indicator["category"] for indicator in result["indicators"]}
        self.assertIn("Emotional", categories)

    def test_executable_attachment_raises_high_risk(self):
        result = analyze(
            "Invoice",
            "Please review the attached file.",
            {
                "attachments": [
                    {
                        "filename": "invoice.exe",
                        "mime_type": "application/octet-stream",
                        "size": 512,
                    }
                ],
                "links": [],
            },
        )

        self.assertEqual(result["risk_tag"], "High")
        self.assertGreater(result["category_scores"]["Attachments"], 0)

    def test_ip_address_link_is_detected(self):
        url = "http://192.168.1.5/login"
        result = analyze(
            "Account review",
            f"Review your account at {url}",
            {"links": [url], "attachments": []},
        )

        evidence = " ".join(
            phrase
            for indicator in result["indicators"]
            for phrase in indicator["phrases"]
        )
        self.assertIn("IP-address link", evidence)
        self.assertGreater(result["category_scores"]["Links"], 0)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        history_path = Path(self.temp_dir.name) / "analysis_history.json"
        self.history_patch = patch.object(app_module, "HISTORY_FILE", history_path)
        self.history_patch.start()
        self.client = create_app().test_client()

    def tearDown(self):
        self.history_patch.stop()
        self.temp_dir.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_analyze_endpoint_returns_explanation(self):
        response = self.client.post(
            "/api/analyze",
            json={
                "subject": "Account verification required",
                "body": "Verify your account immediately or access will be suspended.",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn(payload["risk_tag"], {"Low", "Medium", "High"})
        self.assertIsInstance(payload["indicators"], list)
        self.assertTrue(payload["summary"])


if __name__ == "__main__":
    unittest.main()
