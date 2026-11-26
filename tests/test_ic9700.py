"""
Mode zetten op een (nagebootste) IC-9700 via de echte rigctld van Hamlib. Wordt overgeslagen als rigctld
niet geïnstalleerd is (sudo apt install libhamlib-utils).

    python3 -m unittest discover -s tests
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))

import ax25chat_rig as rig  # noqa: E402


def vrije_poort():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(shutil.which("rigctld"), "rigctld (Hamlib) niet geïnstalleerd")
class TestIc9700(unittest.TestCase):
    def start(self, weiger_26):
        args = [sys.executable, os.path.join(HIER, "nep_ic9700.py")] + (["--weiger-26"] if weiger_26 else [])
        self.nep = subprocess.Popen(args, stdout=subprocess.PIPE, text=True)
        tty = self.nep.stdout.readline().strip()
        self.poort = vrije_poort()
        self.rigctld = subprocess.Popen(["rigctld", "-m", "3081", "-r", tty, "-s", "19200", "-T", "127.0.0.1",
                                         "-t", str(self.poort)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.oud = (rig.POORT, rig.STATION_FILE, rig.LOG_FILE)
        map_ = tempfile.mkdtemp()
        rig.POORT = self.poort
        rig.STATION_FILE, rig.LOG_FILE = os.path.join(map_, "station.json"), os.path.join(map_, "rig_log.json")
        eind = time.time() + 10
        while time.time() < eind and not rig.opdracht("f", timeout=2)[0]:
            time.sleep(0.3)

    def tearDown(self):
        rig.POORT, rig.STATION_FILE, rig.LOG_FILE = self.oud
        for p in (self.rigctld, self.nep):
            p.kill()
            p.wait()

    def station(self, hz, mode="", eigen=()):
        with open(rig.STATION_FILE, "w") as f:
            json.dump({"roepnaam": "PD3PAM-7", "frequentie": hz, "mode": mode, "eigen": list(eigen)}, f)

    def doorloop(self):
        r = {"ptt_methode": "CAT", "cat_model": 3081, "cat_poort": "/dev/x", "cat_mode": "PKTFM"}
        eigen = [{"hz": 144775000, "mode": "PKTUSB", "baud": "1200", "naam": "PD4R"}]
        self.station(144775000, eigen=eigen)                      # eigen frequentie in USB-D
        self.assertEqual(rig.zet_set(r), [])
        st = rig.status()
        self.assertEqual((st["frequentie"], st["mode"]), (144775000, "PKTUSB"))
        self.station(144900000, eigen=eigen)                      # terug naar 144,900: FM-D
        self.assertEqual(rig.zet_set(r), [])
        self.assertEqual(rig._FAMILIE.get(rig.status()["mode"]), "PKTFM")
        rig.zet_mode(r, "PKTUSB")                                 # iemand zet hem op USB-D...
        self.assertIn("teruggezet", rig.bewaak(r) or "")          # ...de bewaker zet hem terug
        self.assertEqual(rig._FAMILIE.get(rig.status()["mode"]), "PKTFM")

    def test_mode_zetten(self):
        self.start(weiger_26=False)
        self.doorloop()

    def test_baken_even_naar_144800(self):
        # Het APRS-baken zet de set even op 144,800 FM-D en daarna terug naar de eigen frequentie (USB-D).
        sys.path.insert(0, os.path.join(HIER, "..", "chat"))
        import ax25chat_baken as baken
        import ax25chat_radio as radio
        self.start(weiger_26=False)
        r = {"ptt_methode": "CAT", "cat_model": 3081, "cat_poort": "/dev/x", "cat_mode": "PKTFM", "geluidskaart": "CODEC"}
        oud = (radio.STATION_FILE, radio.RADIO_FILE)
        radio.STATION_FILE, radio.RADIO_FILE = rig.STATION_FILE, os.path.join(os.path.dirname(rig.STATION_FILE), "radio.json")
        self.addCleanup(lambda: (setattr(radio, "STATION_FILE", oud[0]), setattr(radio, "RADIO_FILE", oud[1])))
        radio.schrijf(radio.RADIO_FILE, r)
        self.station(144775000, eigen=[{"hz": 144775000, "mode": "PKTUSB", "baud": "1200", "naam": "PD4R"}])
        self.assertEqual(rig.zet_set(r), [])
        tijdens = []

        class Chat:
            gepauzeerd = False

        b = baken.Baken(Chat(), start=False, log=lambda t: None, wacht=lambda s: tijdens.append(rig.status()))
        ok, fout = b.via_144800(lambda: True)
        self.assertEqual((ok, fout), (True, ""))
        self.assertEqual((tijdens[0]["frequentie"], rig._FAMILIE.get(tijdens[0]["mode"])), (144800000, "PKTFM"))
        st = rig.status()
        self.assertEqual((st["frequentie"], st["mode"]), (144775000, "PKTUSB"))

    def test_set_weigert_modecommando(self):
        # Hamlib 4.5 zegt dan 'gelukt' maar verandert alleen de datamode; het vangnet (CI-V 0x06) helpt.
        self.start(weiger_26=True)
        self.doorloop()


if __name__ == "__main__":
    unittest.main()
