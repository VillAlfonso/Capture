import unittest
from unittest.mock import Mock
from core import RequestControl, RequestCancelled
from temporary_wifi import TemporaryWifi, Radio


class WifiTests(unittest.TestCase):
    def make(self, reachable):
        backend = Mock()
        backend.candidates.return_value = ['wifi-only']
        backend.radios.return_value = [Radio(0, 2, 1)]
        backend.connected_profile.return_value = 'MAKATI'
        factory = Mock(return_value=backend)
        lease = TemporaryWifi('MAKATI', RequestControl(), factory, reachable)
        return lease, backend, factory

    def test_existing_internet_untouched(self):
        lease, backend, factory = self.make(Mock(return_value=True))
        lease.prepare()
        lease.close()
        factory.assert_not_called()

    def test_offline_connects_and_restores_radio_once(self):
        lease, backend, _ = self.make(Mock(side_effect=[False, True]))
        lease.prepare()
        lease.close()
        lease.close()
        backend.connect.assert_called_once_with('wifi-only', 'MAKATI')
        backend.disconnect.assert_called_once_with('wifi-only')
        self.assertEqual([call.args[2] for call in backend.set_radio.call_args_list], [1, 2])

    def test_failed_connect_cleans_up(self):
        lease, backend, _ = self.make(Mock(return_value=False))
        backend.connect.side_effect = OSError(5, 'failed')
        try:
            with self.assertRaises(OSError):
                lease.prepare()
        finally:
            lease.close()
        backend.disconnect.assert_called_once()
        self.assertEqual(backend.set_radio.call_args.args[2], 2)

    def test_cancellation_cleans_up(self):
        lease, backend, _ = self.make(Mock(return_value=False))
        backend.connect.side_effect = lambda *args: lease.control.cancel()
        try:
            with self.assertRaises(RequestCancelled):
                lease.prepare()
        finally:
            lease.close()
        backend.disconnect.assert_called_once()

    def test_manual_network_change_preserved(self):
        lease, backend, _ = self.make(Mock(side_effect=[False, True]))
        lease.prepare()
        backend.connected_profile.return_value = 'another-profile'
        lease.close()
        backend.disconnect.assert_not_called()
        self.assertEqual(backend.set_radio.call_count, 1)

    def test_missing_profile_does_not_connect(self):
        lease, backend, _ = self.make(Mock(return_value=False))
        backend.candidates.return_value = []
        try:
            with self.assertRaises(RuntimeError):
                lease.prepare()
        finally:
            lease.close()
        backend.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
