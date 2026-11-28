"""
Tests voor de knop Over (venster met info) en de keuze waar de kaart vandaan komt (auto/offline/online).

    python3 -m unittest tests.test_over
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("AX25CHAT_MAP", tempfile.mkdtemp(prefix="ax25chat-over-"))
HIER = os.path.dirname(os.path.abspath(__file__))
for deel in ("chat", "gemeenschappelijk"):
    sys.path.insert(0, os.path.join(HIER, "..", deel))
import ax25chat_kaart as kaart  # noqa: E402
import ax25chat_kaartpagina as kaartpagina  # noqa: E402
import ax25chat_over as over  # noqa: E402


class TestOver(unittest.TestCase):
    def test_dialoog(self):
        h = over.html_dialoog("0.4")
        for moet in ("<dialog id=\"over\"", "0.4", "Gert de Haan", "Claude.AI", "mailto:", "EUPL-1.2", "Direwolf",
                     "github.com/ieddev/AX25Chat", "Sluiten"):
            self.assertIn(moet, h)

    def test_app_gelijk(self):
        """De Android-app (android/.../Over.kt) toont dezelfde gegevens als de webpagina."""
        with open(os.path.join(HIER, "..", "android", "app", "src", "main", "java", "nl", "ied", "ax25chat",
                               "Over.kt"), encoding="utf-8") as f:
            kt = f.read()
        for naam in ("NAAM", "OMSCHRIJVING", "MAKERS", "EMAIL", "GITHUB", "LICENTIE"):
            self.assertIn(f'const val {naam} = "{getattr(over, naam)}"', kt)
        for n, wat, lic, url in over.ONDERDELEN:
            self.assertIn(f'Onderdeel("{n}", "{wat}", "{lic}", "{url}")', kt)


class TestKaartbron(unittest.TestCase):
    def setUp(self):
        kaart.BRON_FILE = os.path.join(tempfile.mkdtemp(), "kaartbron.txt")

    def test_standaard_automatisch(self):
        self.assertEqual(kaart.kaartbron(), "auto")
        d = kaart.voor_kaart()
        self.assertEqual(d["kaartbron"], "auto")
        self.assertIn("pdok", d["online_url"])

    def test_opslaan(self):
        self.assertEqual(kaart.zet_kaartbron("online"), "")
        self.assertEqual(kaart.kaartbron(), "online")
        self.assertTrue(kaart.zet_kaartbron("iets"))
        self.assertEqual(kaart.kaartbron(), "online")

    def test_melding_geen_kaart_alleen_bij_offline(self):
        self.assertNotIn("Nog geen offline kaart", kaartpagina.html_pagina({"kaart": False, "kaartbron": "auto"}))
        self.assertIn("Nog geen offline kaart", kaartpagina.html_pagina({"kaart": False, "kaartbron": "offline"}))


class TestOnderbrokenDownload(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        kaart.BRON_FILE = os.path.join(d, "kaartbron.txt")
        kaart.VOORTGANG_FILE = os.path.join(d, "voortgang.json")
        kaart._schrijf(kaart.VOORTGANG_FILE, {"bezig": True, "bijgewerkt": 1, "fout": ""})   # lang geleden blijven hangen

    def test_geen_rode_melding(self):
        self.assertTrue(kaart.voortgang()["onderbroken"])
        self.assertFalse(kaart.voortgang().get("fout"))

    def test_alleen_online_geen_melding(self):
        kaart.zet_kaartbron("online")
        self.assertNotIn("niet afgemaakt", kaart.html_beheer(""))

    def test_offline_rustige_melding(self):
        kaart.zet_kaartbron("offline")
        h = kaart.html_beheer("")
        self.assertIn("niet afgemaakt", h)
        self.assertNotIn("melding fout", h)


if __name__ == "__main__":
    unittest.main()
