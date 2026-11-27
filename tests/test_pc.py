"""
Tests voor AX25Chat op een PC (pc/ax25chat_pc.py): het programma start Direwolf zelf, houdt een eigen
logboek bij en de webpagina werkt zonder inloggen op localhost. Met een nep-Direwolf (shellscript).

    python3 -m unittest discover -s tests
"""

import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
START = os.path.join(HIER, "..", "pc", "ax25chat_pc.py")

NEP_DIREWOLF = """#!/bin/sh
echo "Dire Wolf (nep) $*"
echo "PD4R-12 audio level = 48(12/10)   [NONE]   |||||____"
trap 'echo gestopt; exit 0' TERM
while true; do sleep 0.2; done
"""


def vrije_poort():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(sys.platform == "win32", "nep-Direwolf is een shellscript")
class TestPc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = tempfile.mkdtemp(prefix="ax25chat-pc-")
        nep = os.path.join(cls.map, "nep-direwolf")
        with open(nep, "w") as f:
            f.write(NEP_DIREWOLF)
        os.chmod(nep, os.stat(nep).st_mode | stat.S_IEXEC)
        with open(os.path.join(cls.map, "direwolf.conf"), "w") as f:
            f.write("ADEVICE plughw:CARD=CODEC,DEV=0\nKISSPORT 8001\nAGWPORT 8000\nMAXV22 0\n")
        with open(os.path.join(cls.map, "station.json"), "w") as f:
            json.dump({"roepnaam": "PD3PAM", "frequentie": 144900000}, f)
        with open(os.path.join(cls.map, "radio_instellingen.json"), "w") as f:
            json.dump({"geluidskaart": "CODEC", "ptt_methode": "VOX"}, f)
        cls.poort = vrije_poort()
        env = dict(os.environ, AX25CHAT_MAP=cls.map, AX25CHAT_DIREWOLF=nep, AX25CHAT_SOORT="pc",
                   AX25CHAT_AMIXER="true", AX25CHAT_RIGCTL="false")
        for k in ("AX25CHAT_SYSTEMCTL", "AX25CHAT_SUDO"):
            env.pop(k, None)
        cls.proc = subprocess.Popen([sys.executable, START, "--geen-browser", "--poort", str(cls.poort)], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        eind = time.time() + 15
        while time.time() < eind:
            try:
                cls.haal("/status.json")
                break
            except OSError:
                time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        cls.proc.stdout.close()
        # Direwolf moet mee gestopt zijn (anders houdt hij de geluidskaart bezet)
        time.sleep(0.5)
        over = subprocess.run(["pgrep", "-f", os.path.join(cls.map, "nep-direwolf")], capture_output=True, text=True)
        assert not over.stdout.strip(), "Direwolf draait nog na het afsluiten"

    @classmethod
    def haal(cls, pad):
        with urllib.request.urlopen(f"http://127.0.0.1:{cls.poort}{pad}", timeout=10) as r:
            return r.read().decode("utf-8")

    def wacht_op(self, functie, seconden=10):
        eind = time.time() + seconden
        while time.time() < eind:
            if functie():
                return True
            time.sleep(0.2)
        return False

    def test_direwolf_draait(self):
        self.assertTrue(self.wacht_op(lambda: json.loads(self.haal("/status.json"))["direwolf"] == "active"))

    def test_status_zonder_inloggen_en_zonder_pi(self):
        html = self.haal("/status")                   # geen 401: lokaal hoeft niet ingelogd te worden
        self.assertIn("Diensten", html)
        self.assertNotIn("Wifi-hotspot", html)
        self.assertNotIn("Pi uitschakelen", html)
        self.assertIn(self.map, html)                 # waar de instellingen staan

    def test_eigen_logboek(self):
        pad = os.path.join(self.map, "logboek", "ax25chat-direwolf.log")
        def staat_erin():
            if not os.path.exists(pad):
                return False
            with open(pad, encoding="utf-8") as f:
                return "audio level" in f.read()
        self.assertTrue(self.wacht_op(staat_erin))
        self.assertIn("PD4R-12 audio level", self.haal("/deel/log"))
        self.assertIn("PD4R-12", self.haal("/deel/gehoord"))

    def test_leaflet_uit_de_programmamap(self):
        self.assertIn("Leaflet", self.haal("/leaflet/leaflet.js")[:2000])


@unittest.skipIf(sys.platform == "win32", "zelfde opzet als hierboven")
class TestThuisnetwerk(unittest.TestCase):
    """--thuisnetwerk: telefoon en app moeten inloggen, maar op de PC zelf (venster) hoeft dat niet."""

    def test_lokaal_geen_inlog(self):
        map_ = tempfile.mkdtemp(prefix="ax25chat-pc-thuis-")
        with open(os.path.join(map_, "web_wachtwoord.json"), "w") as f:
            json.dump({"gebruiker": "beheer", "zout": "AAAA", "hash": "AAAA", "rondes": 1}, f)
        poort = vrije_poort()
        env = dict(os.environ, AX25CHAT_MAP=map_, AX25CHAT_SOORT="pc", AX25CHAT_DIREWOLF="false")
        p = subprocess.Popen([sys.executable, START, "--geen-browser", "--thuisnetwerk", "--poort", str(poort)], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            eind, html = time.time() + 15, ""
            while time.time() < eind and not html:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{poort}/status", timeout=5) as r:
                        html = r.read().decode()
                except OSError:
                    time.sleep(0.2)
            self.assertIn("Diensten", html)
        finally:
            p.terminate()
            p.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
