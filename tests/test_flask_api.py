import csv
import io
import tempfile
import unittest
from pathlib import Path

import api


class FlaskApiTestCase(unittest.TestCase):
    def setUp(self):
        api.app.config.update(TESTING=True)
        self.client = api.app.test_client()

    def test_cors_header_is_present(self):
        response = self.client.get(
            "/api/health",
            headers={"Origin": "https://client.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Access-Control-Allow-Origin", response.headers)

    def test_invalid_query_parameter_returns_400(self):
        response = self.client.get("/api/nodes?min_flood_depth=khong-phai-so")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"], "invalid_query")
        self.assertTrue(payload["message"])

    def test_unknown_and_repeated_query_parameters_return_400(self):
        self.assertEqual(self.client.get("/api/charts?sai_tham_so=1").status_code, 400)
        self.assertEqual(self.client.get("/api/charts?limit=5&limit=10").status_code, 400)

    def test_non_finite_number_returns_400(self):
        self.assertEqual(self.client.get("/api/charts?min_flood_depth=NaN").status_code, 400)

    def test_empty_filter_returns_an_explicit_state(self):
        response = self.client.get("/api/charts?q=__khong_co_nut_nao__")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 0)
        self.assertTrue(payload["empty"])
        self.assertTrue(payload["message"])

    def test_chart_export_returns_csv(self):
        response = self.client.get("/api/charts/export.csv?chart=flood_depth")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("ID", [column.lstrip("\ufeff") for column in rows[0]])

    def test_upload_requires_a_csv_file(self):
        response = self.client.post("/api/data/upload", data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_query")

    def test_valid_upload_is_activated_after_validation(self):
        original_file, original_nodes = api.DATA_FILE, api.NODES
        source = original_file.read_bytes()
        try:
            with tempfile.TemporaryDirectory() as folder:
                api.DATA_FILE = Path(folder) / "Bang thong ke.csv"
                response = self.client.post(
                    "/api/data/upload",
                    data={"file": (io.BytesIO(source), "du-lieu.csv")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(api.DATA_FILE.exists())
                self.assertEqual(response.get_json()["records"], len(api.NODES))
        finally:
            api.DATA_FILE, api.NODES = original_file, original_nodes


if __name__ == "__main__":
    unittest.main()
