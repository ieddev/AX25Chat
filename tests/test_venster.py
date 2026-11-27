"""
Tests voor pc/ax25chat_venster.py zonder venster: poortkeuze als 8080 bezet is, en de opties voor webview.start.

    python3 -m unittest tests.test_venster
"""

import os
import socket
import sys
import tempfile
import unittest

os.environ.setdefault("AX25CHAT_MAP", tempfile.mkdtemp(prefix="ax25chat-venster-"))
HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "pc"))
import ax25chat_venster as venster  # noqa: E402


class TestPoort(unittest.TestCase):
    def setUp(self):
        self.bezet = socket.socket()
        self.bezet.bind(("127.0.0.1", 0))
        self.bezet.listen()
        self.poort = self.bezet.getsockname()[1]
        self._oud = venster.poort_uit
        venster.poort_uit = lambda args: self.poort if "--poort" not in args else self._oud(args)

    def tearDown(self):
        venster.poort_uit = self._oud
        self.bezet.close()

    def test_bezet_door_ander_programma_neemt_vrije_poort(self):
        poort, args = venster.kies_poort([])
        self.assertNotEqual(poort, self.poort)
        self.assertEqual(args, ["--poort", str(poort)])
        self.assertTrue(venster.poort_vrij(poort))

    def test_vaste_poort_bij_thuisnetwerk(self):
        self.assertEqual(venster.kies_poort(["--thuisnetwerk"]), (self.poort, ["--thuisnetwerk"]))

    def test_vrije_poort_blijft(self):
        self.bezet.close()
        self.assertEqual(venster.kies_poort([]), (self.poort, []))


class TestStartOpties(unittest.TestCase):
    def test_alleen_bekende_opties(self):
        class Oud:
            @staticmethod
            def start(func=None):
                pass

        class Nieuw:
            @staticmethod
            def start(func=None, storage_path=None, icon=None):
                pass

        self.assertEqual(venster.start_opties(Oud), {})
        opties = venster.start_opties(Nieuw)
        self.assertTrue(opties["storage_path"].endswith("webview"))
        if sys.platform == "win32":
            self.assertNotIn("icon", opties)          # WinForms wil een .ico; zonder neemt hij dat van de exe
        else:
            self.assertEqual(opties["icon"], venster.PICTOGRAM)


class TestExtern(unittest.TestCase):
    def test_alleen_mailto_en_https(self):
        import webbrowser
        geopend = []
        oud = webbrowser.open
        webbrowser.open = lambda url: geopend.append(url) or True
        try:
            api = venster.VensterApi()
            self.assertTrue(api.extern("mailto:iemand@voorbeeld.nl"))
            self.assertTrue(api.extern("https://github.com/ieddev/AX25Chat"))
            self.assertFalse(api.extern("file:///etc/passwd"))
            self.assertFalse(api.extern("javascript:alert(1)"))
        finally:
            webbrowser.open = oud
        self.assertEqual(geopend, ["mailto:iemand@voorbeeld.nl", "https://github.com/ieddev/AX25Chat"])


if __name__ == "__main__":
    unittest.main()
