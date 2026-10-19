import unittest

from binance_pump_alerts.monitor import Monitor
from binance_pump_alerts.price_tracker import PriceTracker
from binance_pump_alerts.settings import Settings


class FakeApi:
    def __init__(self):
        self.price_map = {"BTCUSDT": 100.0, "ETHUSDT": 100.0, "XRPUSDT": 100.0}

    def usdt_perpetual_symbols(self):
        return {"BTCUSDT", "ETHUSDT", "XRPUSDT"}

    def quote_volumes(self):
        # BTC and ETH pass the 30M filter, XRP does not
        return {"BTCUSDT": 40e6, "ETHUSDT": 31e6, "XRPUSDT": 5e6}

    def prices(self):
        return dict(self.price_map)


class PriceTrackerTest(unittest.TestCase):
    def test_change_percent_and_window(self):
        tracker = PriceTracker()
        tracker.add("A", 100.0, now=0, window_sec=300)
        self.assertIsNone(tracker.change_percent("A"))  # one sample is not enough
        tracker.add("A", 105.0, now=100, window_sec=300)
        self.assertAlmostEqual(tracker.change_percent("A"), 5.0)
        tracker.add("A", 105.0, now=500, window_sec=300)  # first two samples fall out of the window
        self.assertIsNone(tracker.change_percent("A"))    # only one sample left in the window
        tracker.add("A", 105.0, now=510, window_sec=300)
        self.assertAlmostEqual(tracker.change_percent("A"), 0.0)

    def test_retain_only(self):
        tracker = PriceTracker()
        tracker.add("A", 1.0, 0, 300)
        tracker.add("B", 1.0, 0, 300)
        tracker.retain_only({"A"})
        tracker.add("B", 2.0, 1, 300)
        self.assertIsNone(tracker.change_percent("B"))  # B history was dropped


class MonitorTest(unittest.TestCase):
    def make_monitor(self, api, alerts, settings):
        return Monitor(
            api=api,
            load_settings=lambda: settings,
            notify=lambda symbol, change, price, window: alerts.append((symbol, round(change, 2), price)),
            log=lambda text: None,
            set_status=lambda text: None,
        )

    def test_alert_only_for_high_volume_pumping_coin(self):
        api, alerts, settings = FakeApi(), [], Settings()
        monitor = self.make_monitor(api, alerts, settings)

        monitor.tick(settings, now=1000)            # baseline prices
        api.price_map["BTCUSDT"] = 104.5            # +4.5% -> alert
        api.price_map["ETHUSDT"] = 103.0            # +3% -> no alert
        api.price_map["XRPUSDT"] = 150.0            # +50% but volume too low -> no alert
        monitor.tick(settings, now=1060)

        self.assertEqual(alerts, [("BTCUSDT", 4.5, 104.5)])

    def test_cooldown_prevents_repeated_alerts(self):
        api, alerts, settings = FakeApi(), [], Settings(cooldown_minutes=15)
        monitor = self.make_monitor(api, alerts, settings)

        monitor.tick(settings, now=1000)
        api.price_map["BTCUSDT"] = 105.0
        monitor.tick(settings, now=1015)            # alert
        api.price_map["BTCUSDT"] = 106.0
        monitor.tick(settings, now=1030)            # still pumping, but in cooldown
        self.assertEqual(len(alerts), 1)

        api.price_map["BTCUSDT"] = 110.0
        monitor.tick(settings, now=1900)            # new baseline, cooldown (until 1915) not over yet
        api.price_map["BTCUSDT"] = 120.0
        monitor.tick(settings, now=1916)            # +9% and cooldown is over -> second alert
        self.assertEqual(len(alerts), 2)

    def test_volume_setting_is_respected(self):
        api, alerts = FakeApi(), []
        settings = Settings(min_volume_million_usdt=1.0)  # now XRP passes too
        monitor = self.make_monitor(api, alerts, settings)

        monitor.tick(settings, now=1000)
        api.price_map["XRPUSDT"] = 150.0
        monitor.tick(settings, now=1015)
        self.assertEqual([a[0] for a in alerts], ["XRPUSDT"])


if __name__ == "__main__":
    unittest.main()
