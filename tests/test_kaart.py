"""
Tests voor de kaart: APRS-posities lezen (gewoon, gecomprimeerd, Mic-E), stations bewaren en de tegels.

    python3 -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))
sys.path.insert(0, os.path.join(HIER, "..", "chat"))

import ax25chat_aprs as aprs  # noqa: E402
import ax25chat_chat as chat  # noqa: E402
import ax25chat_kaart as kaart  # noqa: E402


def mic_e(lat, lon, knopen=0, koers=0, symbool=">", tabel="/"):
    """Mic-E-frame maken (bestemming, info) volgens de APRS-specificatie, om het lezen te testen."""
    la, lo = abs(lat), abs(lon)
    graden, minuten = int(la), (la - int(la)) * 60
    cijfers = f"{graden:02d}{int(minuten):02d}{round((minuten - int(minuten)) * 100):02d}"
    best = ""
    for i, c in enumerate(cijfers):
        n = int(c)
        hoog = (i == 3 and lat >= 0) or (i == 4 and (lo >= 100 or lo < 10)) or (i == 5 and lon < 0) or i < 3
        best += chr(ord("P") + n) if hoog else c
    g = int(lo)
    if lo >= 100:
        g -= 100
    d = g + 28 if g >= 10 or lo >= 100 else g + 118
    m = int((lo - int(lo)) * 60)
    h = round(((lo - int(lo)) * 60 - m) * 100)
    sp, dc, se = knopen // 10 + 28, (knopen % 10) * 10 + koers // 100 + 28, koers % 100 + 28
    info = "`" + "".join(chr(x) for x in (d, m + 28, h + 28, sp, dc, se)) + symbool + tabel + "Test"
    return best, info


class TestPosities(unittest.TestCase):
    def test_gewoon(self):
        p = aprs.lees_positie("=5212.34N/00612.34E>088/036AX25Chat")
        self.assertAlmostEqual(p["lat"], 52 + 12.34 / 60, places=4)
        self.assertAlmostEqual(p["lon"], 6 + 12.34 / 60, places=4)
        self.assertEqual((p["symbool"], p["koers"], p["kmh"], p["commentaar"]), ("/>", 88, 67, "AX25Chat"))

    def test_met_tijd_en_zuid_west(self):
        p = aprs.lees_positie("@092345z4903.50S\\07201.75W-Thuis")
        self.assertLess(p["lat"], 0)
        self.assertLess(p["lon"], 0)
        self.assertEqual((p["symbool"], p["koers"]), ("\\-", None))

    def test_zoals_ons_baken(self):
        import ax25chat_baken as baken
        p = aprs.lees_positie(baken.aprs_positie(52.25, 6.16, ">", "AX25Chat", 90, 50))
        self.assertAlmostEqual(p["lat"], 52.25, places=3)
        self.assertAlmostEqual(p["lon"], 6.16, places=3)
        self.assertEqual(p["koers"], 90)

    def test_gecomprimeerd(self):          # voorbeeld uit de APRS-specificatie
        p = aprs.lees_positie("=/5L!!<*e7>7P[Hallo")
        self.assertAlmostEqual(p["lat"], 49.5, places=3)
        self.assertAlmostEqual(p["lon"], -72.75, places=3)
        self.assertEqual((p["koers"], p["commentaar"]), (88, "Hallo"))

    def test_mic_e(self):
        for lat, lon, kn, krs in ((52.2551, 6.1634, 0, 0), (52.1, 105.5, 20, 251), (-33.4125, -112.13, 55, 10)):
            best, info = mic_e(lat, lon, kn, krs)
            p = aprs.lees_positie(info.encode("latin-1"), best + "-0")
            self.assertAlmostEqual(p["lat"], lat, places=3, msg=(best, info))
            self.assertAlmostEqual(p["lon"], lon, places=3, msg=(best, info))
            self.assertEqual(p["symbool"], "/>")
            if kn:
                self.assertEqual((p["koers"], p["kmh"]), (krs, round(kn * 1.852)))

    def test_geen_positie(self):
        for info in (":PD3PAM-7 :Hoi{1", ">Status", "", "!0000.00N/00000.00E-", "=99xx.xxN/", "T#001,1,2,3"):
            self.assertIsNone(aprs.lees_positie(info), info)


class NepLink:
    mycall = ""

    def send_info(self, info, dest=None, via=()):
        return True


class TestStations(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp()
        self.opslag = chat.Opslag(os.path.join(self.map, "berichten.db"))
        self.chat = chat.Chat(self.opslag, lambda: {"roepnaam": "PD3PAM-7"}, link=NepLink(), log=lambda t: None)
        self.gemeld = []
        self.chat.luister(lambda soort, d: self.gemeld.append((soort, d)))

    def test_gehoorde_positie_op_de_kaart(self):
        self.chat.ontvangen("PA1ABC-9", "APDR16", ["PI1APD*", "WIDE2-1"], b"=5212.34N/00612.34E>Mobiel")
        s = self.opslag.stations()
        self.assertEqual(len(s), 1)
        self.assertEqual((s[0]["call"], s[0]["direct"], s[0]["via"], s[0]["commentaar"]), ("PA1ABC-9", 0, "PI1APD", "Mobiel"))
        self.assertIn("station", [x[0] for x in self.gemeld])
        self.chat.ontvangen("PA1ABC-9", "APDR16", [], b"=5213.00N/00613.00E>Mobiel")      # nieuwe positie vervangt de oude
        s = self.opslag.stations()
        self.assertEqual((len(s), s[0]["direct"]), (1, 1))

    def test_bericht_is_geen_station(self):
        self.chat.ontvangen("PA1ABC-9", "APDR16", [], b":PD3PAM-7 :Hoi{3")
        self.assertEqual(self.opslag.stations(), [])

    def test_oude_stations_weg(self):
        pos = aprs.lees_positie("=5212.34N/00612.34E>")
        self.opslag.station_toe("PA1OUD", [], pos, nu=1000)
        self.opslag.station_toe("PA1NIEUW", [], pos, nu=1000 + 8 * 86400)
        self.assertEqual([s["call"] for s in self.opslag.stations()], ["PA1NIEUW"])


class TestTegels(unittest.TestCase):
    def test_aantal_redelijk(self):
        n, mb = kaart.schatting(52.255, 6.163, kaart.STANDAARD_STRAAL, kaart.STANDAARD_ZOOM)
        self.assertTrue(3000 < n < kaart.MAX_TEGELS, n)
        tegels = kaart.alle_tegels(52.255, 6.163, 50, 14)
        self.assertEqual(max(t[0] for t in tegels), kaart.DETAIL_ZOOM)       # rond het midden meer detail
        self.assertEqual(min(t[0] for t in tegels), kaart.REGIO_ZOOM[0])

    def test_tegel_pad_veilig(self):
        for z, x, y in (("../..", "1", "1.png"), ("14", "-1", "2.png"), ("14", "1", "x.png"), ("30", "1", "1.png")):
            self.assertIsNone(kaart.tegel_pad(z, x, y))

    def test_download_zonder_plaats(self):
        self.assertTrue(kaart.start_download("", 50, 14, None))
        self.assertTrue(kaart.start_download("Deventer", 7, 14))


if __name__ == "__main__":
    unittest.main()
