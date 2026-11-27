"""
Tests voor ax25chat_systeem.py: de laag die weet op welke computer AX25Chat draait.

    python3 -m unittest discover -s tests
"""

import importlib
import os
import stat
import sys
import tempfile
import time
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


@unittest.skipIf(sys.platform == "win32", "nep-programma is een shellscript")
class TestPcDiensten(unittest.TestCase):
    """PC: het programma start, herstart en stopt zelf een dienst, en houdt het logboek bij."""

    def setUp(self):
        self.map = tempfile.mkdtemp(prefix="ax25chat-pcdienst-")
        self.s = laad(AX25CHAT_SOORT="pc", AX25CHAT_MAP=self.map)
        self.s.OPNIEUW_NA = 0.3
        self.prog = nep(self.map, "prog", 'echo "hallo $$"; trap "exit 0" TERM; while true; do sleep 0.1; done')
        self.nodig = True
        self.s.meld_dienst("test", lambda: [self.prog] if self.nodig else None)

    def tearDown(self):
        self.s.stop_diensten()
        laad()

    def wacht(self, stand, seconden=5):
        eind = time.time() + seconden
        while time.time() < eind and self.s.dienst_status("test") != stand:
            time.sleep(0.05)
        return self.s.dienst_status("test")

    def test_start_herstart_stop(self):
        self.assertEqual(self.s.dienst_status("test"), "inactive")
        self.assertEqual(self.s.start_diensten(), [])
        self.assertEqual(self.wacht("active"), "active")
        eerste = self.s._DIENSTEN["test"]["proc"].pid
        self.assertEqual(self.s.dienst("restart", "test"), (True, ""))
        self.assertEqual(self.wacht("active"), "active")
        self.assertNotEqual(self.s._DIENSTEN["test"]["proc"].pid, eerste)
        self.s.dienst("stop", "test")
        self.assertEqual(self.s.dienst_status("test"), "inactive")
        time.sleep(0.2)
        log = self.s.logboek("test")
        self.assertEqual(log.count("hallo "), 2)
        self.assertIn("2", self.s.logboek("test", regels=1, met_tijd=True)[:4])    # regel begint met het jaartal

    def test_vanzelf_opnieuw_na_vastlopen(self):
        self.s.start_diensten()
        self.assertEqual(self.wacht("active"), "active")
        self.s._DIENSTEN["test"]["proc"].kill()
        time.sleep(0.1)
        self.assertEqual(self.wacht("active"), "active")
        self.assertIn("gestopt", self.s.logboek("test"))

    def test_niet_nodig(self):
        self.nodig = False
        self.s.start_diensten()
        self.assertEqual(self.wacht("niet nodig"), "niet nodig")

    def test_programma_ontbreekt(self):
        self.prog = os.path.join(self.map, "bestaat-niet")
        self.s.start_diensten()
        self.assertEqual(self.wacht("failed"), "failed")
        self.assertIn("starten lukte niet", self.s.logboek("test"))


if __name__ == "__main__":
    unittest.main()
