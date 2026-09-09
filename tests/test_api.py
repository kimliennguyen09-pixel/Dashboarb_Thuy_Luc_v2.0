import unittest
import api


class DashboardDataTest(unittest.TestCase):
    def test_dataset_loaded(self):
        self.assertEqual(len(api.NODES), 139)

    def test_summary_is_consistent(self):
        result = api.summary()
        self.assertEqual(sum(result["risks"].values()), result["total_nodes"])
        self.assertGreaterEqual(result["max_flow"], result["avg_flow"])

    def test_derived_metrics_exist(self):
        self.assertTrue(all("HGL Margin (m)" in n and "Risk" in n for n in api.NODES))


if __name__ == "__main__":
    unittest.main()
