"""
Tests voor ax25chat_systeem.py: de laag die weet op welke computer AX25Chat draait.

    python3 -m unittest discover -s tests
"""

import importlib
import os
import stat
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))


def laad(**env):
    """ax25chat_systeem opnieuw inlezen met deze omgevingsvariabelen."""
    oud = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        import ax25chat_systeem
        return importlib.reload(ax25chat_systeem)
    finally:
        for k, v in oud.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def nep(map_, naam, inhoud):
    pad = os.path.join(map_, naam)
    with open(pad, "w") as f:
        f.write("#!/bin/sh\n" + inhoud + "\n")
    os.chmod(pad, os.stat(pad).st_mode | stat.S_IEXEC)
    return pad


class TestSoort(unittest.TestCase):
    def tearDown(self):
        laad()

    def test_pi(self):
        s = laad(AX25CHAT_SOORT="pi")
        self.assertTrue(s.IS_PI)
        for wat in ("hotspot", "bijwerken_wifi", "uitzetten"):
            self.assertTrue(s.kan(wat), wat)

    def test_pc(self):
        s = laad(AX25CHAT_SOORT="pc")
        self.assertFalse(s.IS_PI)
        for wat in ("hotspot", "bijwerken_wifi", "uitzetten"):
            self.assertFalse(s.kan(wat), wat)
        self.assertEqual(s.dienst_status("ax25chat-direwolf"), "onbekend")
        self.assertFalse(s.dienst("restart", "ax25chat-direwolf")[0])
        self.assertEqual(s.logboek("ax25chat-direwolf", regels=5), "")
        self.assertFalse(s.pi_uitzetten("uit"))


@unittest.skipIf(sys.platform == "win32", "nep-programma's zijn shellscripts")
class TestPi(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp(prefix="ax25chat-systeem-")
        self.log = os.path.join(self.map, "aanroepen")
        schrijf = f'printf "%s\\n" "$*" >> {self.log}'
        self.s = laad(AX25CHAT_SOORT="pi",
                      AX25CHAT_SUDO=nep(self.map, "sudo", schrijf),
                      AX25CHAT_SYSTEMCTL=nep(self.map, "systemctl", schrijf + "; echo active"),
                      AX25CHAT_JOURNALCTL=nep(self.map, "journalctl", schrijf + "; echo regel"))

    def tearDown(self):
        laad()

    def aanroepen(self):
        with open(self.log) as f:
            return f.read().splitlines()

    def test_dienst(self):
        self.assertEqual(self.s.dienst("restart", "ax25chat-direwolf"), (True, ""))
        self.assertEqual(self.s.dienst_status("ax25chat-direwolf"), "active")
        self.assertEqual(self.aanroepen()[0], f"-n {self.s.SYSTEMCTL} restart ax25chat-direwolf")

    def test_logboek(self):
        self.assertEqual(self.s.logboek("ax25chat-direwolf", regels=40).strip(), "regel")
        self.s.logboek("ax25chat-direwolf", uren=24, met_tijd=True)
        self.s.logboek("ax25chat-direwolf", sinds="2026-11-27 12:00:00")
        self.assertEqual(self.aanroepen(), [
            "-u ax25chat-direwolf --no-pager -o cat -n 40",
            "-u ax25chat-direwolf --no-pager -o short-iso --since -24h",
            "-u ax25chat-direwolf --no-pager -o cat --since 2026-11-27 12:00:00"])


if __name__ == "__main__":
    unittest.main()
