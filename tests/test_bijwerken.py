"""
Tests voor bijwerken vanaf de webpagina en de hotspot tijdelijk uit (thuis-wifi). Zonder echte Pi:
sudo, systemctl, nmcli, ip en git worden nagebootst met kleine scripts.

    python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="ax25chat-bijwerken-")
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))
sys.path.insert(0, os.path.join(HIER, "..", "chat"))

import ax25chat_bijwerken as bw  # noqa: E402
import ax25chat_radio as radio   # noqa: E402

BIN = os.path.join(TMP, "bin")
AANROEPEN = os.path.join(TMP, "aanroepen")


def nep(naam, inhoud):
    pad = os.path.join(BIN, naam)
    with open(pad, "w") as f:
        f.write("#!/bin/bash\n" + inhoud + "\n")
    os.chmod(pad, 0o755)
    return pad


class TestBijwerken(unittest.TestCase):
    def setUp(self):
        os.makedirs(BIN, exist_ok=True)
        open(AANROEPEN, "w").close()
        self.oud = (radio.SUDO, radio.SYSTEMCTL, os.environ["PATH"], bw.LOG, bw.THUISWIFI_STAND, radio.MAP)
        radio.MAP = os.path.join(TMP, "map")
        os.makedirs(radio.MAP, exist_ok=True)
        radio.SUDO = nep("sudo", f'printf "%s\\n" "$*" >> {AANROEPEN}; exit ${{NEP_SUDO_RC:-0}}')
        radio.SYSTEMCTL = nep("systemctl", 'echo "${NEP_ACTIEF:-inactive}"')
        nep("nmcli", 'printf "preconfigured:802-11-wireless\\nWired connection 1:802-3-ethernet\\n"')
        nep("ip", 'echo "3: wlan0    inet 192.168.1.57/24 brd 192.168.1.255 scope global wlan0"')
        nep("git", 'echo "abcdef1234567890\trefs/heads/main"')
        os.environ["PATH"] = BIN + os.pathsep + os.environ["PATH"]
        bw.LOG = os.path.join(TMP, "bijwerken.log")
        bw.THUISWIFI_STAND = os.path.join(TMP, "thuiswifi")
        for p in (bw.LOG, bw.THUISWIFI_STAND):
            if os.path.exists(p):
                os.remove(p)
        os.environ.pop("NEP_SUDO_RC", None)
        os.environ.pop("NEP_ACTIEF", None)
        bw._GESTART[0] = 0.0

    def tearDown(self):
        radio.SUDO, radio.SYSTEMCTL, os.environ["PATH"], bw.LOG, bw.THUISWIFI_STAND, radio.MAP = self.oud

    def aanroepen(self):
        with open(AANROEPEN) as f:
            return f.read().splitlines()

    def test_hotspot_uit_en_aan(self):
        self.assertEqual(bw.thuiswifi_naam(), "preconfigured")
        soort, inhoud = bw.verwerk({"stap": "hotspot_uit"}, "")
        self.assertEqual(soort, "html")
        self.assertIn("preconfigured", inhoud)
        bw.verwerk({"stap": "hotspot_aan"}, "")
        self.assertEqual(self.aanroepen(), [
            f"-n {radio.SYSTEMCTL} start --no-block ax25chat-wifi@thuiswifi",
            f"-n {radio.SYSTEMCTL} start --no-block ax25chat-wifi@hotspot"])

    def test_alleen_bekende_acties(self):
        self.assertTrue(bw.wifi_actie("rm -rf"))
        self.assertEqual(self.aanroepen(), [])

    def test_nog_niet_bijgewerkt(self):
        os.environ["NEP_SUDO_RC"] = "1"        # sudo-regel nog van de oude installatie
        soort, waar, melding = bw.verwerk({"stap": "hotspot_uit"}, "")
        self.assertEqual((soort, waar), ("naar", "/status"))
        self.assertIn("ax25chat-bijwerken", melding)

    def test_sectie_hotspot_of_thuiswifi(self):
        h = bw.html_sectie("")
        self.assertIn("Hotspot tijdelijk uitschakelen", h)
        with open(bw.THUISWIFI_STAND, "w") as f:
            f.write("preconfigured\n")
        h = bw.html_sectie("")
        self.assertIn("Thuis-wifi actief: preconfigured", h)
        self.assertIn("http://192.168.1.57", h)
        self.assertIn("Hotspot nu weer aanzetten", h)

    def test_controleren(self):
        with open(os.path.join(radio.MAP, "versie.txt"), "w") as f:
            f.write("abcdef1 2026-11-25\n")
        self.assertIn("al de nieuwste versie", bw.html_controle(""))
        with open(os.path.join(radio.MAP, "versie.txt"), "w") as f:
            f.write("1111111 2026-11-20\n")
        self.assertIn("Er is een nieuwe versie: <b>abcdef1</b>", bw.html_controle(""))
        nep("git", "exit 128")
        self.assertIn("geen internet", bw.html_controle(""))

    def test_starten_en_verslag(self):
        self.assertEqual(bw.verwerk({"stap": "start"}, ""), ("naar", "/bijwerken", ""))
        self.assertIn(f"-n {radio.SYSTEMCTL} start --no-block ax25chat-bijwerken", self.aanroepen())
        d = json.loads(bw.als_json())
        self.assertTrue(d["bezig"])                       # verslag is er nog niet
        with open(bw.LOG, "w") as f:
            f.write("== START\n\x1b[1;34m== Pakketten\x1b[0m\n== EINDE 0\n")
        d = json.loads(bw.als_json())
        self.assertEqual((d["bezig"], d["einde"]), (False, 0))
        self.assertNotIn("\x1b", d["log"])
        with open(bw.LOG, "w") as f:
            f.write("FOUT: ophalen van GitHub mislukt (internet?).\n== EINDE 3\n")
        self.assertIn("mislukt", bw.html_sectie(""))


class TestScripts(unittest.TestCase):
    def test_bash_syntax(self):
        d = os.path.join(HIER, "..", "gemeenschappelijk", "diensten")
        for s in ("ax25chat-wifi.sh", "ax25chat-bijwerken.sh"):
            self.assertEqual(subprocess.run(["bash", "-n", os.path.join(d, s)]).returncode, 0, s)
        self.assertEqual(subprocess.run(["bash", "-n", os.path.join(HIER, "..", "installeer.sh")]).returncode, 0)

    def test_sudoregel_past_bij_webpagina(self):
        with open(os.path.join(HIER, "..", "installeer.sh"), encoding="utf-8") as f:
            inst = f.read()
        for eenheid in ("ax25chat-bijwerken", "ax25chat-wifi@thuiswifi", "ax25chat-wifi@hotspot"):
            self.assertIn(f"$SC start --no-block {eenheid}", inst)


if __name__ == "__main__":
    unittest.main()
