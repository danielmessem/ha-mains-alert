import unittest
from mains_alert.detector import MainsDetector


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"mode": "numeric", "off_threshold": 50, "on_threshold": 180,
                    "off_delay": 15, "on_delay": 10}

    def test_outage_and_restore_are_debounced(self):
        d = MainsDetector()
        self.assertIsNone(d.update(230, 0, self.cfg).event)
        self.assertIsNone(d.update(0, 1, self.cfg).event)
        self.assertIsNone(d.update(0, 15, self.cfg).event)
        self.assertEqual(d.update(0, 16, self.cfg).event, "off")
        self.assertIsNone(d.update(230, 20, self.cfg).event)
        self.assertEqual(d.update(230, 30, self.cfg).event, "on")

    def test_deadband_does_not_change_status(self):
        d = MainsDetector()
        d.update(230, 0, self.cfg)
        self.assertEqual(d.update(100, 5, self.cfg).condition, "unknown")
        self.assertEqual(d.status, "on")

    def test_text_states(self):
        cfg = {"mode": "state", "off_values": ["off", "unavailable"], "on_values": ["on"], "off_delay": 0}
        d = MainsDetector()
        d.update("ON", 0, cfg)
        d.update("unavailable", 1, cfg)
        self.assertEqual(d.update("unavailable", 1, cfg).event, "off")


if __name__ == "__main__":
    unittest.main()

