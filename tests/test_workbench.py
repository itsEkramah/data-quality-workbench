import csv
import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from qualitydesk.app import create_app
from qualitydesk.engine import Rules, clean_csv, export_csv


class CleaningTests(unittest.TestCase):
    def test_quarantine_does_not_claim_duplicate_key(self):
        result = clean_csv("id,amount,date\na,NaN,2026-11-14\na,12.50,2026-11-14\na,5,2026-11-14\nb,2,14/11/2026\n",
                           Rules(required=["id", "amount", "date"], key=["id"], numeric=["amount"], dates=["date"]))
        self.assertEqual(result["summary"]["input_rows"], 4)
        self.assertEqual(result["summary"]["accepted_rows"], 1)
        self.assertEqual(result["summary"]["rejected_rows"], 3)
        self.assertEqual(result["accepted"][0]["amount"], "12.50")

    def test_structure_and_rules_are_validated(self):
        for text, rules in [("a,a\n1,2", Rules()), ("a\n1", Rules(required=["absent"])),
                            ("a\n1", Rules(nonnegative=["a"]))]:
            with self.assertRaises(ValueError):
                clean_csv(text, rules)

    def test_row_width_and_formula_export(self):
        result = clean_csv("name,n\n=SUM(A1),1\nb,2,3\n", Rules())
        self.assertEqual(result["summary"]["rejected_rows"], 1)
        rows = list(csv.reader(io.StringIO(export_csv(result))))
        self.assertEqual(rows[1][0], "'=SUM(A1)")


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.db"
        self.client = TestClient(create_app(self.db))

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_persist_download_and_delete(self):
        response = self.client.post("/api/jobs", json={"csv_text": "id,amount\na,5\na,7\n", "rules": {"key": ["id"]}})
        self.assertEqual(response.status_code, 201)
        job_id = response.json()["id"]
        second = TestClient(create_app(self.db))
        self.assertEqual(second.get(f"/api/jobs/{job_id}").json()["summary"]["rejected_rows"], 1)
        self.assertEqual(second.get(f"/api/jobs/{job_id}/export?kind=source").text, "id,amount\na,5\na,7\n")
        self.assertIn("duplicate accepted key", second.get(f"/api/jobs/{job_id}/export?kind=rejected").text)
        self.assertEqual(second.delete(f"/api/jobs/{job_id}").status_code, 204)
        self.assertEqual(second.get(f"/api/jobs/{job_id}").status_code, 404)
        second.close()

    def test_bad_rule_is_a_client_error(self):
        response = self.client.post("/api/jobs", json={"csv_text": "id\na", "rules": {"key": ["no"]}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
