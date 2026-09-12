import unittest
from mains_alert.detector import MainsDetector
from mains_alert.discovery import mobile_notify_services, rank_mains_entities


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


class DiscoveryTests(unittest.TestCase):
    def test_grid_voltage_beats_pv_and_battery(self):
        states = [
            {"entity_id": "sensor.deye_pv_voltage", "state": "320", "attributes": {"friendly_name": "Deye PV Voltage", "unit_of_measurement": "V"}},
            {"entity_id": "sensor.deye_battery_voltage", "state": "52", "attributes": {"friendly_name": "Battery voltage", "unit_of_measurement": "V"}},
            {"entity_id": "sensor.deye_grid_voltage", "state": "231", "attributes": {"friendly_name": "Deye Grid Voltage", "unit_of_measurement": "V"}},
        ]
        self.assertEqual(rank_mains_entities(states)[0]["entity_id"], "sensor.deye_grid_voltage")

    def test_only_mobile_notify_services_are_returned(self):
        services = [{"domain": "notify", "services": {"mobile_app_dan": {}, "persistent_notification": {}, "mobile_app_guest": {}}}]
        self.assertEqual(mobile_notify_services(services), ["notify.mobile_app_dan", "notify.mobile_app_guest"])


if __name__ == "__main__":
    unittest.main()
