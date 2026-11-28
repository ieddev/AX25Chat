"""
Tests voor AX25Chat op een PC (pc/ax25chat_pc.py): het programma start Direwolf zelf, houdt een eigen
logboek bij en de webpagina werkt zonder inloggen op localhost. Met een nep-Direwolf (shellscript).

    python3 -m unittest discover -s tests
"""

import base64
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
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



def eigen_ip():
    """Een adres van deze computer dat niet 127.0.0.1 is (om 'van buiten' te testen), of None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


class TestTelefoon(unittest.TestCase):
    """Status -> Telefoon en app: aanzetten met een wachtwoord, dan ook op het thuisnetwerk; uit = alleen de PC."""

    def setUp(self):
        self.map = tempfile.mkdtemp(prefix="ax25chat-pc-tel-")
        with open(os.path.join(self.map, "station.json"), "w") as f:
            json.dump({"roepnaam": "PD3PAM", "frequentie": 144900000}, f)
        self.poort = vrije_poort()
        env = dict(os.environ, AX25CHAT_MAP=self.map, AX25CHAT_SOORT="pc", AX25CHAT_DIREWOLF="false",
                   AX25CHAT_FIREWALL="0")     # Windows: in de test geen firewallregel (en geen UAC-vraag)
        self.p = subprocess.Popen([sys.executable, START, "--geen-browser", "--poort", str(self.poort)], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertIn("Telefoon en app", self.haal("127.0.0.1", "/status", wacht=15))

    def tearDown(self):
        self.p.terminate()
        self.p.wait(timeout=10)

    def haal(self, ip, pad, wacht=0, kop=None):
        eind = time.time() + wacht
        while True:
            try:
                req = urllib.request.Request(f"http://{ip}:{self.poort}{pad}", headers=kop or {})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.read().decode("utf-8")
            except urllib.error.HTTPError as fout:
                return f"HTTP {fout.code}"
            except OSError:
                if time.time() > eind:
                    raise
                time.sleep(0.2)

    def post(self, velden):
        html = self.haal("127.0.0.1", "/status")
        csrf = html.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        data = urllib.parse.urlencode(dict(velden, csrf=csrf)).encode()
        with urllib.request.urlopen(f"http://127.0.0.1:{self.poort}/telefoon", data, timeout=15) as r:
            return r.read().decode("utf-8")

    def test_aan_en_uit(self):
        ip = eigen_ip()
        self.assertIn("Uit.", self.haal("127.0.0.1", "/status"))
        uit = self.post({"actie": "aan"})                      # zonder wachtwoord: weigeren
        self.assertIn("Kies eerst een wachtwoord", urllib.parse.unquote(uit) + uit)
        self.assertFalse(os.path.exists(os.path.join(self.map, "telefoon.json")))
        uit = self.post({"actie": "aan", "ww1": "geheim123", "ww2": "geheim123"})
        self.assertIn("Aan.", uit)
        self.assertIn("bereikbaar vanaf je telefoon", uit)
        with open(os.path.join(self.map, "telefoon.json")) as f:
            self.assertTrue(json.load(f)["aan"])
        self.assertIn("Diensten", self.haal("127.0.0.1", "/status"))   # op de PC zelf: geen inlog
        if ip:
            self.assertEqual(self.haal(ip, "/status"), "HTTP 401")       # telefoon: Status met wachtwoord
            kop = {"Authorization": "Basic " + base64.b64encode(b"beheer:geheim123").decode()}
            self.assertIn("Diensten", self.haal(ip, "/status", kop=kop))
            self.assertIn("berichten", self.haal(ip, "/api/berichten"))  # de app: zonder wachtwoord, zoals op de Pi
            self.assertIn("roepnaam", self.haal(ip, "/status.json"))
        self.post({"actie": "uit"})
        self.assertIn("Uit.", self.haal("127.0.0.1", "/status"))
        if ip:
            with self.assertRaises(OSError):
                self.haal(ip, "/status.json")


class TestFirewall(unittest.TestCase):
    """Windows: de netsh-opdracht voor de firewallregel (zonder hem uit te voeren)."""

    def test_opdracht(self):
        sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))
        import ax25chat_telefoon as tel
        o = tel.firewall_opdracht(8080)
        for stuk in ('name="AX25Chat (telefoon, poort 8080)"', "dir=in", "action=allow", "protocol=TCP",
                     "localport=8080", "profile=private"):
            self.assertIn(stuk, o)
        self.assertNotIn("program=", o)                  # alleen in het Windows-programma (frozen)
        oud = getattr(sys, "frozen", None)
        sys.frozen = True
        try:
            self.assertIn(f'program="{sys.executable}"', tel.firewall_opdracht(8099))
        finally:
            if oud is None:
                del sys.frozen
            else:
                sys.frozen = oud

    def test_niet_buiten_windows_of_in_tests(self):
        import ax25chat_telefoon as tel
        oud = os.environ.get("AX25CHAT_FIREWALL")
        os.environ["AX25CHAT_FIREWALL"] = "0"
        try:
            self.assertFalse(tel.firewall_nodig())
            self.assertEqual(tel.firewall_open(8080), "")
        finally:
            if oud is None:
                os.environ.pop("AX25CHAT_FIREWALL")
            else:
                os.environ["AX25CHAT_FIREWALL"] = oud


if __name__ == "__main__":
    unittest.main()
