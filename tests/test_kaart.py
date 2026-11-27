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
import ax25chat_locator as locator  # noqa: E402


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

    def test_locator_uit_baken(self):
        self.chat.ontvangen("PD4R-12", "ALL", [], b"PD4R-12  Warnsveld  JO32CD  144.925 1k2")
        self.assertEqual([(r["call"], r["locator"]) for r in self.opslag.locators()], [("PD4R-12", "JO32CD")])
        self.assertIn("locator", [x[0] for x in self.gemeld])
        self.assertEqual(self.opslag.stations(), [])                   # geen APRS-positie
        self.chat.ontvangen("PD4R-12", "ID", [], ASCII_ART.encode())  # getekende letters: niets herkend
        self.assertEqual(len(self.opslag.locators()), 1)
        self.assertIn("PD4R-12", self.opslag.gehoord())

    def test_aprs_positie_en_bericht_geen_locator(self):
        self.chat.ontvangen("PA1ABC-9", "APDR16", [], b"=5212.34N/00612.34E>Thuis in JO32CD")
        self.chat.ontvangen("PA1ABC-9", "APDR16", [], b":PD3PAM-7 :Mijn locator is JO22AB{4")
        self.assertEqual(self.opslag.locators(), [])

    def test_oude_stations_weg(self):
        pos = aprs.lees_positie("=5212.34N/00612.34E>")
        self.opslag.station_toe("PA1OUD", [], pos, nu=1000)
        self.opslag.station_toe("PA1NIEUW", [], pos, nu=1000 + 8 * 86400)
        self.assertEqual([s["call"] for s in self.opslag.stations()], ["PA1NIEUW"])


ASCII_ART = r""" _  _   __   ____  __ _  ____  _  _  ____  __
/ )( \ / _\ (  _ \(  ( \/ ___)/ )( \(  __)(  )
\ /\ //    \ )   //    /\___ \\ \/ / ) _) / (_/
(_/\_)\_/\_/(__\_)\_)__)(____/ \__/ (____)\____"""


class TestLocator(unittest.TestCase):
    def test_vak_en_midden(self):
        self.assertEqual(locator.vak("JO32CD"), (52.125, 6.166667, 52.166667, 6.25))
        lat, lon = locator.midden("jo32cd")
        self.assertAlmostEqual(lat, 52.14583, places=4)            # Warnsveld ligt op 52,13 N 6,23 O
        self.assertAlmostEqual(lon, 6.20833, places=4)
        self.assertEqual(locator.vak("JO32"), (52, 6, 53, 8))
        z, w, n, o = locator.vak("JO32CD45")
        self.assertAlmostEqual(n - z, 0.25 / 60, places=6)
        for fout in ("", "JZ32", "JO3", "JO32CZ", "JO32CD4", "PD4R", "12AB34"):
            self.assertIsNone(locator.vak(fout), fout)

    def test_zoek_in_baken(self):
        for tekst, loc in (("PD4R-12 Warnsveld JO32CD 144.925 1k2", "JO32CD"), ("BPQ node, loc: jo32cd", "JO32CD"),
                           ("Node Warnsveld QTH JO32", "JO32"), ("LOC=JO32 438.175 9k6", "JO32"),
                           ("Locator JO32CD45", "JO32CD45")):
            self.assertEqual(locator.zoek(tekst), loc, tekst)

    def test_geen_valse_locator(self):
        for tekst in ("PD4R-12 IC9700 FT818 PA3ABC", "AB12 is geen locator", "XJO32CDY", "JO32CD5", ASCII_ART,
                      "PD3PAM-7>APZAXC 144.925"):
            self.assertEqual(locator.zoek(tekst), "", tekst)

    def test_zelf_invullen(self):
        s = {}
        self.assertEqual(locator.zet_handmatig(s, "pd4r-12", "jo32cd"), "")
        self.assertEqual(locator.handmatig(s), {"PD4R-12": "JO32CD"})
        self.assertTrue(locator.zet_handmatig(s, "PD4R-12", "XX99"))
        self.assertTrue(locator.zet_handmatig(s, "a", "JO32CD"))
        self.assertEqual(locator.zet_handmatig(s, "PD4R-12", ""), "")
        self.assertEqual(locator.handmatig(s), {})


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


class TestViaSsh(unittest.TestCase):
    """ax25chat-kaart via ssh: zonder internet even naar de thuis-wifi, en verder na een onderbreking."""

    def setUp(self):
        self.oud = (kaart.KAART_DIR, kaart.TEGELS, kaart.NIEUW, kaart.INFO_FILE, kaart.VOORTGANG_FILE,
                    kaart.internet, kaart.thuiswifi, kaart.start_met_thuiswifi, sys.argv)
        d = tempfile.mkdtemp()
        kaart.KAART_DIR, kaart.TEGELS, kaart.NIEUW = d, os.path.join(d, "tegels"), os.path.join(d, "tegels.nieuw")
        kaart.INFO_FILE, kaart.VOORTGANG_FILE = os.path.join(d, "kaart.json"), os.path.join(d, "voortgang.json")
        kaart.internet = lambda timeout=8: False
        self.gestart = []
        kaart.start_met_thuiswifi = lambda naam: self.gestart.append(naam) or 0

    def tearDown(self):
        (kaart.KAART_DIR, kaart.TEGELS, kaart.NIEUW, kaart.INFO_FILE, kaart.VOORTGANG_FILE,
         kaart.internet, kaart.thuiswifi, kaart.start_met_thuiswifi, sys.argv) = self.oud

    def test_geen_internet_wel_thuiswifi(self):
        kaart.thuiswifi = lambda: ("Thuis", True)
        sys.argv = ["ax25chat-kaart", "--midden", "52.25,6.16"]
        self.assertEqual(kaart.main(), 0)
        self.assertEqual(self.gestart, ["Thuis"])

    def test_geen_internet_geen_thuiswifi(self):
        kaart.thuiswifi = lambda: (None, True)
        sys.argv = ["ax25chat-kaart", "--midden", "52.25,6.16"]
        self.assertEqual(kaart.main(), 1)
        self.assertEqual(self.gestart, [])
        self.assertIn("Geen internet", kaart.voortgang()["fout"])

    def test_niet_wisselen(self):
        kaart.thuiswifi = lambda: ("Thuis", True)
        sys.argv = ["ax25chat-kaart", "Deventer", "--niet-wisselen"]
        self.assertEqual(kaart.main(), 1)
        self.assertEqual(self.gestart, [])

    def test_verder_na_onderbreking(self):
        pad = os.path.join(kaart.NIEUW, "14", "8472", "5390.png")
        os.makedirs(os.path.dirname(pad))
        with open(pad, "wb") as f:
            f.write(b"png")
        self.assertTrue(kaart._haal((14, 8472, 5390), kaart.NIEUW, kaart.TEGELS))      # niet opnieuw gehaald
