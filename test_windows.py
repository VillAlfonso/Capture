"""Native event handlers tested with fabricated events, no installed hooks."""
import ctypes as C
import unittest
from unittest.mock import patch
import app


class WindowsTests(unittest.TestCase):
    def setUp(self):
        self.instance = app.App({'allowed_processes': ['pycharm64.exe']})
        self.forward = patch.object(app.U, 'CallNextHookEx', return_value=77)
        self.focus = patch.object(app.U, 'GetForegroundWindow', return_value=123)
        self.allowed = patch('app.foreground_allowed', return_value=123)
        for mock in (self.forward, self.focus, self.allowed):
            mock.start()
            self.addCleanup(mock.stop)

    def key(self, vk, down=True, flags=0):
        event = app.KB(vk=vk, flags=flags)
        return self.instance.keyboard(0, 0x100 if down else 0x101, C.addressof(event))

    def test_cancel_clears_capture_queue_and_frees_slot(self):
        instance = self.instance
        control = app.RequestControl()
        instance.request_control = control
        instance.busy = True
        instance.png = b'capture'
        instance.work.put(('send', instance.buffer.epoch, None))
        instance.buffer.accept(instance.buffer.epoch, 'old answer')
        instance.cancel_pending()
        self.assertTrue(control.cancelled.is_set())
        self.assertFalse(instance.busy)
        self.assertIsNone(instance.png)
        self.assertTrue(instance.work.empty())
        self.assertEqual(instance.buffer.text, '')
        new_control = app.RequestControl()
        instance.request_control = new_control
        instance.busy = True
        with patch('app.read_key', return_value='test'):
            instance.request(instance.buffer.epoch - 1, b'old', control)
        self.assertIs(instance.request_control, new_control)
        self.assertTrue(instance.busy)

    def test_repeat_and_keyup_suppression(self):
        self.assertEqual(self.key(0xA5), 1)
        self.assertEqual(self.key(81), 1)
        self.assertEqual(self.key(81), 1)
        self.assertEqual(self.instance.work.qsize(), 1)
        self.assertEqual(self.key(0xA5, False), 1)
        self.assertEqual(self.key(81, False), 1)
        self.assertEqual(self.key(81), 77)

    def test_release_rehold_preserves_position_and_discards_old_taps(self):
        self.instance.buffer.accept(self.instance.buffer.epoch, 'abc')
        def consume():
            _, epoch, value = self.instance.work.get_nowait()
            self.instance.replay_character(epoch, value)
        with patch('app.send_character', return_value=True) as send:
            self.key(0xA5)
            self.key(81)
            consume()
            self.key(81, False)
            self.key(82)
            self.key(0xA5, False)
            self.assertEqual(self.instance.buffer.index, 1)
            # Held-letter repeats must not leak into the editor after Alt release.
            self.assertEqual(self.key(82), 1)
            self.key(82, False)
            self.assertEqual(self.key(83), 77)
            self.key(0xA5)
            consume()  # queued tap from previous hold must not consume 'b'
            self.assertEqual(self.instance.buffer.index, 1)
            self.key(84)
            consume()
            self.assertEqual(self.instance.buffer.index, 2)
            self.assertEqual([c.args[0] for c in send.call_args_list], ['a', 'b'])

    def test_injected_events_do_not_recurse(self):
        self.key(0xA5)
        self.assertEqual(self.key(81, flags=0x10), 77)
        self.assertTrue(self.instance.work.empty())

    def test_focus_change_stops_queue(self):
        self.key(0xA5)
        app.U.GetForegroundWindow.return_value = 456
        self.assertEqual(self.key(81), 1)
        self.assertTrue(self.instance.work.empty())

    def test_other_app_retains_right_alt(self):
        with patch('app.foreground_allowed', return_value=0):
            self.assertEqual(self.key(0xA5), 77)
        self.assertEqual(self.key(81), 77)

    def test_capture_uses_release_point(self):
        start = app.MS(pt=app.W.POINT(100, 150), data=1 << 16)
        end = app.MS(pt=app.W.POINT(-20, 30), data=1 << 16)
        self.assertEqual(self.instance.mouse(0, 0x20B, C.addressof(start)), 1)
        self.assertEqual(self.instance.mouse(0, 0x20C, C.addressof(end)), 1)
        action, epoch, box = self.instance.work.get_nowait()
        self.assertEqual((action, box), ('capture', (-20, 30, 100, 150)))

    def test_input_structures_unicode_and_newline(self):
        self.assertEqual(C.sizeof(app.INPUT), 40 if C.sizeof(C.c_void_p) == 8 else 28)
        batches = []
        def send(count, inputs, size):
            batches.append([(inputs[i].ki.vk, inputs[i].ki.scan, inputs[i].ki.flags) for i in range(count)])
            return count
        with patch.object(app.U, 'SendInput', side_effect=send):
            self.assertTrue(app.send_character('a'))
            self.assertTrue(app.send_character('\n'))
            self.assertTrue(app.send_character('\U0001f600'))
        self.assertEqual(batches[0], [(0, 97, 4), (0, 97, 6)])
        self.assertEqual(batches[1], [(13, 0, 0), (13, 0, 2)])
        self.assertEqual(len(batches[2]), 4)


if __name__ == '__main__':
    unittest.main()
