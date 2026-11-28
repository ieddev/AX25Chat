"""
Tests voor Bijwerken op een PC (ax25chat_pcbijwerken.py): Linux via git, Windows via de releases op GitHub.
Zonder internet: een eigen git-'origin' en een nagebootste releaselijst.

    python3 -m unittest discover -s tests
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))

import ax25chat_pcbijwerken as pb  # noqa: E402


def git(map_, *args):
    subprocess.run(["git", "-C", map_, *args], check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                            GIT_COMMITTER_EMAIL="t@t"))


@unittest.skipUnless(shutil.which("git"), "git niet geïnstalleerd")
class TestGit(unittest.TestCase):
    def setUp(self):
        t = tempfile.mkdtemp(prefix="ax25chat-pcbw-")
        self.bron, self.kopie = os.path.join(t, "bron"), os.path.join(t, "AX25Chat")
        os.makedirs(self.bron)
        git(self.bron, "init", "-q", "-b", "main")
        pathlib.Path(self.bron, "a.txt").write_text("1")
        git(self.bron, "add", "-A")
        git(self.bron, "commit", "-q", "-m", "eerste")
        subprocess.run(["git", "clone", "-q", self.bron, self.kopie], check=True)
        self.oud = (pb.REPO, pb.soort, pb.herstart_later)
        pb.REPO = self.kopie
        pb.soort = lambda: "git"
        self.herstart = []
        pb.herstart_later = lambda *a: self.herstart.append(1)

    def tearDown(self):
        pb.REPO, pb.soort, pb.herstart_later = self.oud

    def test_niets_nieuw(self):
        self.assertFalse(pb.controleer()["nieuw"])
        self.assertEqual(pb.html_balk(), "")

    def test_stil_zonder_internet(self):
        """De controle die vanzelf gaat: lukt fetch niet, dan geen foutmelding op de pagina en geen balk."""
        pb.controleer()
        oud = pb.GIT
        pb.GIT = "false"
        try:
            uit = pb.controleer(stil=True)
        finally:
            pb.GIT = oud
        self.assertTrue(uit.get("fout"))
        self.assertNotIn("lukte niet", pb.html_sectie(""))
        self.assertEqual(pb.html_balk(), "")

    def test_automatisch(self):
        pathlib.Path(self.bron, "a.txt").write_text("3")
        git(self.bron, "commit", "-q", "-am", "nieuw")
        oud = pb.internet
        pb.internet = lambda *a: True
        try:
            t = pb.start_automatisch(eerst=0, elke=3600)
            for _ in range(100):
                if pb.nieuw():
                    break
                import time
                time.sleep(0.1)
        finally:
            pb.internet = oud
        self.assertIsNotNone(t)
        self.assertIn("Bijwerken", pb.html_balk())

    def test_nieuwe_versie_ophalen_en_herstarten(self):
        pathlib.Path(self.bron, "a.txt").write_text("2")
        git(self.bron, "commit", "-q", "-am", "Kaart: menu boven de kaart")
        uit = pb.controleer()
        self.assertTrue(uit["nieuw"])
        self.assertIn("Kaart: menu boven de kaart", uit["wijzigingen"][0])
        self.assertIn("Nu bijwerken", pb.html_sectie(""))
        self.assertIn("Nieuwe versie beschikbaar", pb.html_balk())
        ok, tekst = pb.bijwerken()
        self.assertTrue(ok, tekst)
        self.assertEqual(pathlib.Path(self.kopie, "a.txt").read_text(), "2")
        self.assertEqual(self.herstart, [1])
        self.assertFalse(pb.controleer()["nieuw"])


class TestWindows(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp(prefix="ax25chat-pcbw-win-")
        self.oud = (pb.RELEASES, pb.soort, pb.versie)
        pb.soort = lambda: "windows"

    def tearDown(self):
        pb.RELEASES, pb.soort, pb.versie = self.oud

    def releases(self, *tags):
        pad = os.path.join(self.map, "releases.json")
        with open(pad, "w") as f:
            json.dump([{"tag_name": t, "draft": False,
                        "assets": [{"name": f"AX25Chat-setup-{t[5:]}.exe", "size": 31_000_000,
                                    "browser_download_url": f"https://example.invalid/{t}.exe"}]} for t in tags]
                      + [{"tag_name": "app-v0.9", "draft": False, "assets": []}], f)
        pb.RELEASES = pathlib.Path(pad).as_uri()

    def test_nieuwere_versie(self):
        self.releases("win-v0.1", "win-v0.2")
        pb.versie = lambda: "0.1 (abc1234 2026-11-27)"
        uit = pb.controleer()
        self.assertTrue(uit["nieuw"])
        self.assertEqual(uit["naam"], "AX25Chat-setup-0.2.exe")
        self.assertIn("0.2", uit["tekst"])

    def test_al_nieuwste(self):
        self.releases("win-v0.1", "win-v0.2")
        pb.versie = lambda: "0.2 (abc1234 2026-11-28)"
        self.assertFalse(pb.controleer()["nieuw"])

    def test_testversie_mag_naar_release(self):
        self.releases("win-v0.1")
        pb.versie = lambda: "0.1-test.7 (abc1234 2026-11-27)"
        self.assertTrue(pb.controleer()["nieuw"])

    def test_geen_internet(self):
        pb.RELEASES = pathlib.Path(self.map, "bestaat-niet.json").as_uri()
        pb.versie = lambda: "0.1"
        uit = pb.controleer()
        self.assertTrue(uit.get("fout"))
        self.assertIn("Controleren lukte niet", pb.html_sectie(""))


if __name__ == "__main__":
    unittest.main()
