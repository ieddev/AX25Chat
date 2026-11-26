"""
Tests voor connected mode (BBS): het AGW-protocol, de sessie en de eigen BBS-lijst. Zonder Direwolf.
Met twee echte Direwolfs en een nagebootste BBS: zie tests/nep_bbs.py en docs/TESTPLAN.md.

    python3 -m unittest discover -s tests
"""

import os
import sys
import tempfile
import threading
import time
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))
sys.path.insert(0, os.path.join(HIER, "..", "chat"))

import ax25chat_agw as agw      # noqa: E402
import ax25chat_bbs as bbs      # noqa: E402
import ax25chat_radio as radio  # noqa: E402
import ax25chat_rig as rig      # noqa: E402


class NepAgw:
    """Doet alsof het de AGW-poort van Direwolf is: onthoudt wat er gestuurd wordt."""

    def __init__(self):
        self.gestuurd = []
        self.verbonden = threading.Event()
        self.verbonden.set()

    def _s(self, *x):
        self.gestuurd.append(x)
        return True

    def aanmelden(self, mijn):
        return self._s("X", mijn)

    def afmelden(self, mijn):
        return self._s("x", mijn)

    def verbind(self, mijn, naar, via=()):
        return self._s("C", mijn, naar)

    def tekst(self, mijn, naar, data):
        return self._s("D", mijn, naar, data)

    def verbreek(self, mijn, naar):
        return self._s("d", mijn, naar)


class Basis(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp()
        self.oud = (radio.STATION_FILE, rig.STATION_FILE, radio.RADIO_FILE)
        radio.STATION_FILE = rig.STATION_FILE = os.path.join(self.map, "station.json")
        radio.RADIO_FILE = os.path.join(self.map, "radio.json")
        radio.schrijf(radio.STATION_FILE, {"roepnaam": "PD3PAM-7", "frequentie": 144900000,
                                           "eigen": [{"hz": 144775000, "mode": "PKTUSB", "baud": "1200", "naam": "PD4R"}]})

    def tearDown(self):
        radio.STATION_FILE, rig.STATION_FILE, radio.RADIO_FILE = self.oud


class TestAgw(unittest.TestCase):
    def test_pakket(self):
        p = agw.pakket("D", "pd3pam-7", "PD4R-1", "L\r", pid=0xF0)
        self.assertEqual(len(p), 36 + 2)
        poort, soort, pid, van, aan, n, _ = agw.KOP.unpack_from(p)
        self.assertEqual((poort, chr(soort), pid, agw._call(van), agw._call(aan), n), (0, "D", 0xF0, "PD3PAM-7", "PD4R-1", 2))

    def test_tekst_van(self):
        self.assertEqual(bbs.tekst_van(b"*** CONNECTED With Station PD4R-1\r\0"), "*** CONNECTED With Station PD4R-1\r")
        self.assertEqual(bbs.tekst_van("Café".encode("latin-1")), "Café")
        self.assertTrue(bbs.zelfde("PD4R-0", "pd4r"))


class TestLijst(Basis):
    def test_toevoegen_en_weghalen(self):
        self.assertEqual(bbs.voeg_toe("pd4r-1", 144775000, "PD4R BBS")[0], [])
        self.assertEqual(bbs.voeg_toe("PD4R-2", 0, "")[0], [])
        self.assertTrue(bbs.voeg_toe("geen call!", 0, "")[0])
        self.assertTrue(bbs.voeg_toe("PD4R-3", 144812500, "")[0])       # niet in de frequentielijst
        lijst = bbs.lijst()
        self.assertEqual([x["call"] for x in lijst], ["PD4R-1", "PD4R-2"])
        self.assertEqual(lijst[0]["tekst"], "144,775 MHz · USB-D · 1200 baud")        # mode van Mijn frequenties
        self.assertEqual(lijst[1]["tekst"], "huidige frequentie")
        bbs.voeg_toe("PD4R-1", 144925000, "")                                         # zelfde call: vervangen
        self.assertEqual(len(bbs.lijst()), 2)
        bbs.haal_weg("pd4r-2")
        self.assertEqual([x["call"] for x in bbs.lijst()], ["PD4R-1"])
        self.assertEqual(radio.station()["eigen"][0]["hz"], 144775000)                # Mijn frequenties blijft


class TestSessie(Basis):
    def maak(self, wissel=None):
        self.link, self.events = NepAgw(), []
        s = bbs.Sessie(radio.station, lambda soort, d: self.events.append(d), wissel=wissel or (lambda hz: ([], False)),
                       link=self.link, log=lambda t: None)
        s._bij_verbinding(True)
        return s

    def test_verbinden_lezen_verbreken(self):
        s = self.maak()
        self.assertEqual(self.link.gestuurd[0], ("X", "PD3PAM-7"))
        self.assertEqual(s.verbind("pd4r-1"), "")
        self.assertEqual(self.link.gestuurd[-1], ("C", "PD3PAM-7", "PD4R-1"))
        self.assertEqual(s.stand, "verbinden")
        self.assertTrue(s.verbind("PD4R-2"))                                       # al bezig
        self.assertTrue(s.stuur("L"))                                              # nog niet verbonden
        s._pakket("C", "PD4R-1", "PD3PAM-7", b"*** CONNECTED With Station PD4R-1\r\0")
        self.assertEqual(s.stand, "verbonden")
        s._pakket("D", "PD4R-1", "PD3PAM-7", b"Welkom\rPD4R BBS >\r")
        s._pakket("D", "PA1ABC", "PD3PAM-7", b"niet voor deze sessie")
        self.assertEqual(s.stuur("L"), "")
        self.assertEqual(self.link.gestuurd[-1], ("D", "PD3PAM-7", "PD4R-1", "L\r"))
        self.assertEqual([(r["soort"], r["tekst"]) for r in s.regels if r["soort"] != "info"],
                         [("in", "Welkom\rPD4R BBS >\r"), ("uit", "L")])
        s._pakket("C", "PA1ABC", "PD3PAM-7", b"*** CONNECTED With Station PA1ABC\r")    # tweede station: weigeren
        self.assertEqual(self.link.gestuurd[-1], ("d", "PD3PAM-7", "PA1ABC"))
        self.assertEqual(s.tegen, "PD4R-1")
        s.verbreek()
        self.assertEqual((s.stand, self.link.gestuurd[-1]), ("verbreken", ("d", "PD3PAM-7", "PD4R-1")))
        s._pakket("d", "PD4R-1", "PD3PAM-7", b"*** DISCONNECTED From Station PD4R-1\r")
        self.assertEqual(s.stand, "verbroken")
        self.assertEqual(self.events[-1]["stand"], "verbroken")

    def test_geen_antwoord(self):
        s = self.maak()
        s.verbind("PD4R-1")
        s._pakket("d", "PD4R-1", "PD3PAM-7", b"*** DISCONNECTED RETRYOUT With PD4R-1\r")
        self.assertEqual(s.stand, "verbroken")
        self.assertIn("Geen antwoord", s.regels[-1]["tekst"])

    def test_direwolf_valt_weg(self):
        s = self.maak()
        s.verbind("PD4R-1")
        s._pakket("C", "PD4R-1", "PD3PAM-7", b"*** CONNECTED With Station PD4R-1\r")
        s._bij_verbinding(False)
        self.assertEqual(s.stand, "verbroken")
        self.link.verbonden.clear()
        self.assertEqual(s.verbind("PD4R-1"), "")
        self.assertEqual(s.stand, "verbroken")                                    # Direwolf niet bereikbaar
        self.assertIn("8000", s.regels[-1]["tekst"])

    def test_frequentie_wisselen(self):
        gewisseld = []

        def wissel(hz):                      # Direwolf herstart (andere snelheid): de AGW-verbinding valt even weg
            gewisseld.append(hz)
            s._bij_verbinding(False)
            s._bij_verbinding(True)
            return [], True
        s = self.maak(wissel)
        self.assertEqual(s.verbind("PD4R-1", 144775000), "")
        eind = time.time() + 5
        while time.time() < eind and self.link.gestuurd[-1][0] != "C":
            time.sleep(0.05)
        self.assertEqual(gewisseld, [144775000])
        self.assertEqual(self.link.gestuurd[-1], ("C", "PD3PAM-7", "PD4R-1"))
        self.assertEqual(s.stand, "verbinden")

    def test_eigen_roepnaam_en_roepnaam_gewijzigd(self):
        s = self.maak()
        self.assertTrue(s.verbind("PD3PAM-7"))
        radio.schrijf(radio.STATION_FILE, dict(radio.station(), roepnaam="PD3PAM-9"))
        s.verbind("PD4R-1")
        self.assertIn(("x", "PD3PAM-7"), self.link.gestuurd)
        self.assertIn(("X", "PD3PAM-9"), self.link.gestuurd)
        self.assertEqual(self.link.gestuurd[-1], ("C", "PD3PAM-9", "PD4R-1"))


class TestWissel(Basis):
    def test_zelfde_snelheid_geen_herstart(self):
        radio.schrijf(radio.RADIO_FILE, {})
        self.assertEqual(bbs.wissel_frequentie(144925000), ([], False))
        self.assertEqual(radio.station()["frequentie"], 144925000)
        self.assertTrue(bbs.wissel_frequentie(144812500)[0])                     # niet in de lijst


if __name__ == "__main__":
    unittest.main()
