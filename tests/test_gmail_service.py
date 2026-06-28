import base64
import unittest

from gmail_service import parse_message


def encode_body(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


class GmailParserTests(unittest.TestCase):
    def test_plain_text_is_preferred_over_html_alternative(self):
        message = {
            "id": "message-1",
            "payload": {
                "headers": [{"name": "Subject", "value": "Test message"}],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": encode_body("Readable plain email")},
                    },
                    {
                        "mimeType": "text/html",
                        "body": {"data": encode_body("<p>HTML alternative</p>")},
                    },
                ],
            },
        }

        parsed = parse_message(message)

        self.assertEqual(parsed["body"], "Readable plain email")

    def test_html_disguised_as_plain_text_is_cleaned(self):
        html = (
            '<table><tr><td style="color:red">Security notice</td></tr></table>'
            '<a href="https://example.com/check">Review account</a>'
        )
        message = {
            "id": "message-2",
            "payload": {
                "headers": [],
                "mimeType": "text/plain",
                "body": {"data": encode_body(html)},
            },
        }

        parsed = parse_message(message)

        self.assertNotIn("<td", parsed["body"])
        self.assertNotIn("style=", parsed["body"])
        self.assertIn("Security notice", parsed["body"])
        self.assertIn("https://example.com/check", parsed["links"])


if __name__ == "__main__":
    unittest.main()
