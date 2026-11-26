"""
Tests voor het APRS-baken: NMEA lezen, het APRS-formaat, wanneer er gebakend wordt, en een GPS op een pty.

    python3 -m unittest discover -s tests
"""

import os
import pty
import sys
import tempfile
import time
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))
sys.path.insert(0, os.path.join(HIER, "..", "chat"))

import ax25chat_baken as baken  # noqa: E402
import ax25chat_radio as radio  # noqa: E402
import ax25chat_rig as rig      # noqa: E402


def nmea(zin):
    som = 0
    for c in zin:
        som ^= ord(c)
    return f"${zin}*{som:02X}"


RMC = nmea("GPRMC,123519,A,5212.3400,N,00612.3400,E,48.6,084.4,261126,,")    # 48,6 knopen = 90 km/h


class NepLink:
    def __init__(self):
        self.mycall, self.verzonden = "", []

    def send_info(self, info, dest=None, via=()):
        self.verzonden.append((self.mycall, dest, list(via), info))
        return True


class NepOpslag:
    def monitor_toe(self, van, aan, pad, info):
        return {"van": van, "info": info}


class NepChat:
    def __init__(self):
        self.link, self.opslag = NepLink(), NepOpslag()

    def mijn_call(self):
        return "PD3PAM-9"

    def _meld(self, soort, data):
        pass


class TestFormaat(unittest.TestCase):
    def test_nmea(self):
        self.assertTrue(baken.nmea_ok(RMC))
        self.assertFalse(baken.nmea_ok(RMC[:-1] + "0"))
        p = baken.lees_rmc(RMC)
        self.assertAlmostEqual(p["lat"], 52 + 12.34 / 60)
        self.assertAlmostEqual(p["lon"], 6 + 12.34 / 60)
        self.assertAlmostEqual(p["kmh"], 90.0, places=0)
        self.assertEqual(p["koers"], 84.4)
        self.assertIsNone(baken.lees_rmc(nmea("GPRMC,123519,V,,,,,,,261126,,")))           # nog geen positie
        self.assertEqual(baken.lees_rmc(nmea("GNRMC,1,A,3351.000,S,15112.000,W,0,,261126,,"))["lon"], -(151 + 12 / 60))

    def test_aprs(self):
        self.assertEqual(baken.aprs_positie(52 + 12.34 / 60, 6 + 12.34 / 60, ">", "AX25Chat"), "=5212.34N/00612.34E>AX25Chat")
        self.assertEqual(baken.aprs_positie(52.2, 6.2, ">", "", 84.4, 90), "=5212.00N/00612.00E>084/049")
        self.assertEqual(baken.aprs_positie(52.2, 6.2, ">", "", 84.4, 2), "=5212.00N/00612.00E>")        # stilstaand: geen koers
        self.assertEqual(baken.aprs_positie(-33.5, -151.2, "-", ""), "=3330.00S/15112.00W-")
        self.assertEqual(baken.aprs_positie(52.99999999, 6.2, ">", "")[1:9], "5300.00N")                  # afronden


class TestWanneer(unittest.TestCase):
    B = {"interval": 20, "slim": True, "stilstaand": False}
    THUIS = {"lat": 52.2, "lon": 6.2, "kmh": 0, "koers": None}

    def pos(self, meter_noord, kmh=50, koers=0):
        return {"lat": 52.2 + meter_noord / 111195, "lon": 6.2, "kmh": kmh, "koers": koers}

    def test_eerste_en_stilstaand(self):
        self.assertEqual(baken.moet_bakenen(1000, 0, self.B, self.THUIS, None, None), "eerste")
        self.assertEqual(baken.moet_bakenen(1000 + 7200, 1000, self.B, self.pos(50, 0), None, self.THUIS), "")   # 50 m: niet verplaatst
        b = dict(self.B, stilstaand=True)
        self.assertEqual(baken.moet_bakenen(1000 + 1800, 1000, b, self.THUIS, None, self.THUIS), "")
        self.assertEqual(baken.moet_bakenen(1000 + 3600, 1000, b, self.THUIS, None, self.THUIS), "stilstaand")

    def test_rijden(self):
        b = dict(self.B, slim=False)
        self.assertEqual(baken.moet_bakenen(1000 + 600, 1000, b, self.pos(5000), 0, self.THUIS), "")          # 10 min: te vroeg
        self.assertEqual(baken.moet_bakenen(1000 + 1200, 1000, b, self.pos(5000), 0, self.THUIS), "interval")
        self.assertEqual(baken.moet_bakenen(1000 + 30, 1000, self.B, self.pos(5000), 0, self.THUIS), "")       # nooit binnen 1 min
        self.assertEqual(baken.moet_bakenen(1000 + 180, 1000, self.B, self.pos(5000, 100), 0, self.THUIS), "rijden")
        self.assertEqual(baken.moet_bakenen(1000 + 180, 1000, self.B, self.pos(5000, 30), 0, self.THUIS), "")  # 30 km/h: elke 9 min
        self.assertEqual(baken.moet_bakenen(1000 + 540, 1000, self.B, self.pos(5000, 30), 0, self.THUIS), "rijden")
        self.assertEqual(baken.moet_bakenen(1000 + 90, 1000, self.B, self.pos(1000, 50, 90), 0, self.THUIS), "bocht")
        self.assertEqual(baken.moet_bakenen(1000 + 90, 1000, self.B, self.pos(1000, 50, 20), 0, self.THUIS), "")  # flauwe bocht


class TestBaken(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp()
        self.oud = (radio.STATION_FILE, rig.STATION_FILE, radio.RADIO_FILE)
        radio.STATION_FILE = rig.STATION_FILE = os.path.join(self.map, "station.json")
        radio.RADIO_FILE = os.path.join(self.map, "radio.json")
        self.zet(rig.APRS_FREQ)
        self.nu, self.bezig = 100000.0, ""
        self.chat = NepChat()
        self.b = baken.Baken(self.chat, start=False, klok=lambda: self.nu, verbonden=lambda: self.bezig,
                                 log=lambda t: None, wacht=lambda s: None)

    def tearDown(self):
        radio.STATION_FILE, rig.STATION_FILE, radio.RADIO_FILE = self.oud

    def zet(self, freq, **baken_inst):
        b = dict(baken.STANDAARD, aan=True, bron="handmatig", lat=52.2, lon=6.2)
        b.update(baken_inst)
        radio.schrijf(radio.STATION_FILE, {"roepnaam": "PD3PAM-9", "frequentie": freq, "baken": b})

    def test_handmatig(self):
        self.assertEqual(self.b.stap(), "=5212.00N/00612.00E>AX25Chat")
        self.assertEqual(self.chat.link.verzonden[0][:3], ("PD3PAM-9", "APZAXC", ["WIDE1-1", "WIDE2-1"]))
        self.nu += 7200
        self.assertEqual(self.b.stap(), "")                                   # zelfde positie: niets
        self.assertIn("wacht tot je positie verandert", self.b.stand)
        self.zet(rig.APRS_FREQ, lat=52.3)                                     # andere positie ingevuld
        self.assertTrue(self.b.stap())
        self.assertTrue(self.b.nu())                                          # knop Nu: altijd
        self.assertEqual(len(self.chat.link.verzonden), 3)

    def test_telefoon(self):
        baken.TELEFOON["pos"] = None
        self.zet(rig.APRS_FREQ, bron="telefoon")
        self.assertEqual(self.b.stap(), "")
        self.assertIn("telefoon", self.b.stand)
        self.assertEqual(baken.telefoon_positie({"lat": "52.25", "lon": 6.16, "kmh": 80, "koers": 90}, nu=self.nu), "")
        self.assertTrue(self.b.stap().startswith("=5215.00N/00609.60E>090/043"))
        self.nu += 120                                                       # app stuurt niets meer: te oud
        self.assertIsNone(self.b.positie(baken.instellingen()))
        self.assertTrue(baken.telefoon_positie({"lat": "x", "lon": 6}))
        self.assertTrue(baken.telefoon_positie({"lat": 0, "lon": 0}))
        f = {"aan": "1", "bron": "telefoon", "interval": "20", "symbool": ">", "pad": "WIDE1-1"}
        self.assertEqual(baken.verwerk(f)[0], [])                            # geen poort of positie nodig
        self.assertEqual(baken.instellingen()["bron"], "telefoon")
        baken.TELEFOON["pos"] = None

    def test_wacht_op_frequentie_en_bbs(self):
        self.zet(144925000)                                                   # geen CAT: kan niet even wisselen
        self.assertEqual(self.b.stap(), "")
        self.assertIn("144,925", self.b.stand)
        self.assertIn("geen CAT", self.b.stand)
        self.zet(rig.APRS_FREQ)
        self.bezig = "PD4R-12"
        self.assertEqual(self.b.stap(), "")
        self.assertIn("Gepauzeerd", self.b.stand)
        self.assertEqual(self.b.nu(), "")                                     # ook Nu niet tijdens een BBS-verbinding
        self.bezig = ""
        self.assertTrue(self.b.stap())

    def met_cat(self, modem=1200):
        """Doe alsof er een IC-9700 met CAT is; onthoud wat er met de set gebeurt."""
        self.set_log = []
        oud = (rig.zet_set, rig.cat_actief, radio.modem, radio.instellingen)
        self.addCleanup(lambda: setattr(rig, "zet_set", oud[0]) or setattr(rig, "cat_actief", oud[1])
                        or setattr(radio, "modem", oud[2]) or setattr(radio, "instellingen", oud[3]))
        rig.zet_set = lambda r, freq=None: self.set_log.append(("set", rig.doelfrequentie(), rig.doelmode(r))) or []
        rig.cat_actief = lambda r: True
        radio.modem = lambda r, doel=None: modem
        radio.instellingen = lambda: {"cat_model": 3081}
        stuur = self.chat.link.send_info

        def send_info(info, dest=None, via=()):
            self.set_log.append(("zend", rig.doelfrequentie(), self.chat.gepauzeerd))
            return stuur(info, dest, via)
        self.chat.link.send_info = send_info

    def test_even_naar_144800(self):
        self.met_cat()
        self.zet(144925000)
        self.assertTrue(self.b.stap())
        self.assertEqual(self.set_log, [("set", 144800000, "PKTFM"),          # even naar 144,800 FM-D
                                        ("zend", 144800000, True),            # zenden; chat wacht
                                        ("set", 144925000, rig.doelmode({}))])  # en terug
        self.assertIsNone(rig.TIJDELIJK)
        self.assertFalse(self.chat.gepauzeerd)
        self.assertFalse(self.b.weg)

    def test_niet_bij_andere_snelheid(self):
        self.met_cat(modem=9600)
        self.zet(438175000)
        self.assertEqual(self.b.stap(), "")
        self.assertIn("9600 baud", self.b.stand)
        self.assertEqual(self.set_log, [])

    def test_uit(self):
        self.zet(rig.APRS_FREQ, aan=False)
        self.assertEqual(self.b.stap(), "")
        self.assertEqual(self.chat.link.verzonden, [])

    def test_verwerk(self):
        fouten, _ = baken.verwerk({"aan": "1", "bron": "handmatig", "lat": "52,1234", "lon": "6,5", "interval": "15",
                                   "symbool": "b", "commentaar": "Op de fiets", "pad": "wide1-1"})
        self.assertEqual(fouten, [])
        b = baken.instellingen()
        self.assertEqual((b["lat"], b["lon"], b["interval"], b["symbool"], b["pad"], b["slim"]),
                         (52.1234, 6.5, 15, "b", "WIDE1-1", False))
        self.assertTrue(baken.verwerk({"aan": "1", "bron": "handmatig"})[0])               # geen positie
        self.assertTrue(baken.verwerk({"lat": "95", "lon": "6"})[0])
        self.assertEqual(radio.station()["frequentie"], rig.APRS_FREQ)                    # Station blijft


class TestGps(unittest.TestCase):
    def test_pty(self):
        moeder, kind = pty.openpty()
        pad = os.ttyname(kind)
        g = baken.Gps(lambda: pad, log=lambda t: None)
        eind = time.time() + 5
        while time.time() < eind and not g.positie():
            os.write(moeder, (nmea("GPGGA,123519,5212.34,N,00612.34,E,1,08,0.9,10.0,M,46.9,M,,") + "\r\n" + RMC + "\r\n").encode())
            time.sleep(0.3)
        p = g.positie()
        self.assertIsNotNone(p)
        self.assertAlmostEqual(p["lat"], 52 + 12.34 / 60)

    def test_is_gps(self):
        moeder, kind = pty.openpty()
        os.write(moeder, (RMC + "\r\n").encode())
        self.assertTrue(baken.is_gps(os.ttyname(kind), 2))
        moeder2, kind2 = pty.openpty()
        os.write(moeder2, b"FA14425000000;\r\n")                  # geen NMEA (bijv. een set)
        self.assertFalse(baken.is_gps(os.ttyname(kind2), 1))


if __name__ == "__main__":
    unittest.main()
