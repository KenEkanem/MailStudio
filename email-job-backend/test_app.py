import io
import unittest

from app import app, personalize, render_email


class EmailJobTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_personalization(self):
        self.assertEqual(personalize("Hi {{name}} — {{ event }}", "Ada Lovelace", "Python Day"), "Hi Ada Lovelace — Python Day")

    def test_rendered_email_contains_content(self):
        subject, html = render_email({"event": "Summit", "subject": "Welcome to {{event}}", "message_html": "Hello {{name}}"}, "Grace Hopper")
        self.assertEqual(subject, "Welcome to Summit")
        self.assertIn("Hello Grace Hopper", html)

    def test_csv_validation(self):
        response = self.client.post("/api/recipients/validate", data={
            "csv": (io.BytesIO(b"first_name,last_name,email\nAda,Lovelace,ada@example.com\n"), "people.csv")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["count"], 1)

    def test_csv_requires_exact_columns(self):
        response = self.client.post("/api/recipients/validate", data={
            "csv": (io.BytesIO(b"name,email\nAda,ada@example.com\n"), "people.csv")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing CSV columns", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
