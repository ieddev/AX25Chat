"""
Tests voor de chat (stap 2): APRS-berichten, bevestigen, herhalen, CQ en de monitor. Zonder Direwolf.

    python3 -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))
sys.path.insert(0, os.path.join(HIER, "..", "chat"))

import ax25chat_chat as chat  # noqa: E402


class NepLink:
    """Doet alsof het Direwolf is: onthoudt wat er verzonden wordt."""

    def __init__(self):
        self.mycall, self.verzonden, self.aan = "", [], True

    def send_info(self, info, dest=None, via=()):
        if self.aan:
            self.verzonden.append((self.mycall, dest, list(via), info))
        return self.aan


class TestFormaat(unittest.TestCase):
    def test_maken_en_lezen(self):
        info = chat.maak_bericht("pa1abc-9", "Hoi", "12")
        self.assertEqual(info, ":PA1ABC-9 :Hoi{12")
        self.assertEqual(chat.lees_bericht(info), {"aan": "PA1ABC-9", "tekst": "Hoi", "nummer": "12", "soort": "bericht"})
        self.assertEqual(chat.lees_bericht(chat.maak_ack("PD3PAM-7", "12"))["soort"], "ack")
        self.assertEqual(chat.lees_bericht(":PD3PAM-7 :ack12}AB")["nummer"], "12")       # reply-ack
        self.assertEqual(chat.lees_bericht(":CQ       :Hallo allemaal")["nummer"], None)
        self.assertIsNone(chat.lees_bericht("!5215.00N/00610.00E-PHG"))                  # positie, geen bericht

    def test_delen_en_schoon(self):
        lang = "woord " * 30
        stukken = chat.delen(lang)
        self.assertTrue(all(len(s) <= 67 for s in stukken))
        self.assertEqual(" ".join(stukken), lang.strip())
        self.assertEqual(chat.schoon("a{b|c~d"), "a(b/c-d")

    def test_zelfde_call(self):
        self.assertTrue(chat.zelfde_call("PD3PAM", "pd3pam-0"))
        self.assertFalse(chat.zelfde_call("PD3PAM", "PD3PAM-7"))


class TestChat(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp()
        self.opslag = chat.Opslag(os.path.join(self.map, "berichten.db"))
        self.station = {"roepnaam": "PD3PAM-7", "pad": "WIDE1-1"}
        self.link = NepLink()
        self.chat = chat.Chat(self.opslag, lambda: self.station, link=self.link, log=lambda t: None)
        self.gemeld = []
        self.chat.luister(lambda soort, data: self.gemeld.append((soort, data)))

    def test_bericht_met_bevestiging(self):
        fouten, [b] = self.chat.verstuur("pa1abc-9", "Hoi, hoor je me?")
        self.assertEqual(fouten, [])
        self.chat.verwerk_wachtrij(nu=1000)
        call, dest, via, info = self.link.verzonden[-1]
        self.assertEqual((call, dest, via), ("PD3PAM-7", "APZAXC", ["WIDE1-1"]))
        self.assertEqual(info, f":PA1ABC-9 :Hoi, hoor je me?{{{b['nummer']}")
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "verzonden")
        self.chat.verwerk_wachtrij(nu=1010)                       # nog niet herhalen
        self.assertEqual(len(self.link.verzonden), 1)
        self.chat.ontvangen("PA1ABC-9", "APDR16", [], f":PD3PAM-7 :ack{b['nummer']}".encode())
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "bevestigd")
        self.chat.verwerk_wachtrij(nu=5000)
        self.assertEqual(len(self.link.verzonden), 1)             # bevestigd: niet meer herhalen

    def test_herhalen_en_mislukt(self):
        _, [b] = self.chat.verstuur("PA1ABC", "Iemand thuis?")
        nu = 1000
        for _ in range(len(chat.WACHTTIJDEN)):
            self.chat.verwerk_wachtrij(nu=nu)
            nu += 200
        self.assertEqual(len(self.link.verzonden), 5)
        self.chat.verwerk_wachtrij(nu=nu)
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "mislukt")
        self.assertTrue(self.chat.opnieuw(b["id"]))
        self.chat.verwerk_wachtrij(nu=nu + 1)
        self.assertEqual(len(self.link.verzonden), 6)

    def test_stoppen(self):
        _, [b] = self.chat.verstuur("PD3F", "Test, hoor je me?")
        self.chat.verwerk_wachtrij(nu=1000)
        self.assertTrue(self.chat.stop(b["id"]))
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "gestopt")
        self.chat.verwerk_wachtrij(nu=5000)
        self.assertEqual(len(self.link.verzonden), 1)             # niet meer herhaald
        self.assertFalse(self.chat.stop(b["id"]))                 # al gestopt
        self.chat.ontvangen("PD3F", "APDR16", [], f":PD3PAM-7 :ack{b['nummer']}".encode())
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "bevestigd")   # late bevestiging telt
        self.assertFalse(self.chat.stop(b["id"]))

    def test_stoppen_en_opnieuw(self):
        _, [b] = self.chat.verstuur("PD3F", "Nog een keer")
        self.chat.stop(b["id"])
        self.chat.verwerk_wachtrij(nu=1000)
        self.assertEqual(self.link.verzonden, [])                 # gestopt voor de eerste uitzending
        self.assertTrue(self.chat.opnieuw(b["id"]))
        self.chat.verwerk_wachtrij(nu=1001)
        self.assertEqual(len(self.link.verzonden), 1)
        self.assertFalse(self.chat.stop(9999))

    def test_direwolf_weg(self):
        self.link.aan = False
        _, [b] = self.chat.verstuur("PA1ABC", "Test")
        self.chat.verwerk_wachtrij(nu=1000)
        self.assertEqual(self.opslag.bericht(b["id"])["pogingen"], 0)   # telt niet als poging
        self.link.aan = True
        self.chat.verwerk_wachtrij(nu=1011)
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "verzonden")

    def test_cq(self):
        _, [b] = self.chat.verstuur("cq", "CQ CQ de PD3PAM")
        self.assertIsNone(b["nummer"])
        self.chat.verwerk_wachtrij(nu=1000)
        self.assertEqual(self.link.verzonden[-1][3], ":CQ       :CQ CQ de PD3PAM")
        self.assertEqual(self.opslag.bericht(b["id"])["status"], "cq")
        self.chat.verwerk_wachtrij(nu=2000)
        self.assertEqual(len(self.link.verzonden), 1)

    def test_ontvangen_met_ack_en_herhaling(self):
        self.chat.ontvangen("PA1ABC-9", "APDR16", ["WIDE1-1*"], b":PD3PAM-7 :Hallo Gert{7")
        self.assertEqual(self.link.verzonden[-1][3], ":PA1ABC-9 :ack7")
        self.chat.ontvangen("PA1ABC-9", "APDR16", [], b":PD3PAM-7 :Hallo Gert{7")      # herhaling
        self.assertEqual(len(self.link.verzonden), 2)                                # opnieuw bevestigd
        inkomend = [b for b in self.opslag.lijst() if b["richting"] == "in"]
        self.assertEqual([(b["van"], b["tekst"]) for b in inkomend], [("PA1ABC-9", "Hallo Gert")])
        self.assertEqual(len(self.opslag.monitor()), 2)

    def test_cq_ontvangen_en_anderen(self):
        self.chat.ontvangen("PA1ABC-9", "APZAXC", [], b":CQ       :CQ de PA1ABC")
        self.chat.ontvangen("PA2XYZ", "APZAXC", [], b":PA1ABC-9 :Niet voor jou{3")     # tussen anderen
        self.chat.ontvangen("PA3QRP", "ID", [], b"PA3QRP/R BBS")                       # gewoon UI-frame
        inkomend = [b for b in self.opslag.lijst() if b["richting"] == "in"]
        self.assertEqual([(b["van"], b["aan"]) for b in inkomend], [("PA1ABC-9", "CQ")])
        self.assertEqual(self.link.verzonden, [])                                      # niets bevestigd
        self.assertEqual(len(self.opslag.monitor()), 3)

    def test_eigen_frame_via_digipeater(self):
        self.chat.ontvangen("PD3PAM-7", "APZAXC", ["WIDE1-1*"], b":CQ       :CQ")
        self.assertEqual(self.opslag.monitor(), [])

    def test_fouten(self):
        self.assertTrue(self.chat.verstuur("", "x")[0])
        self.assertTrue(self.chat.verstuur("PA1ABC", "   ")[0])
        self.station["roepnaam"] = "N0CALL"
        self.assertTrue(self.chat.verstuur("PA1ABC", "x")[0])

    def test_lang_bericht(self):
        _, delen = self.chat.verstuur("PA1ABC", "x" * 150)
        self.assertEqual(len(delen), 3)
        self.assertEqual(len({b["nummer"] for b in delen}), 3)


if __name__ == "__main__":
    unittest.main()
