"""
Tests voor de Pi-kant van AX25Chat, zonder echte hardware.

    python3 -m unittest discover -s tests

Er wordt een nep-/sys, /proc/asound/cards en /dev/serial/by-id gemaakt met de sets van Gert:
IC-9700, IC-7300, FT-818 met SCU-17 en twee DigiRigs (GM-340 en UV-5R).
"""

import array
import os
import shutil
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix="ax25chat-test-")
for k, v in {"AX25CHAT_MAP": os.path.join(TMP, "map"), "AX25CHAT_SYS": os.path.join(TMP, "sys"),
             "AX25CHAT_ASOUND_CARDS": os.path.join(TMP, "cards"),
             "AX25CHAT_SERIAL_BY_ID": os.path.join(TMP, "by-id"),
             "AX25CHAT_SYSTEMCTL": "true", "AX25CHAT_SUDO": "true", "AX25CHAT_RIGCTL": "false"}.items():
    os.environ[k] = v
os.makedirs(os.environ["AX25CHAT_MAP"])
sys.path.insert(0, os.path.join(HIER, "..", "pi"))

import ax25chat_ax25 as ax25    # noqa: E402
import ax25chat_radio as radio  # noqa: E402
import ax25chat_rig as rig      # noqa: E402
import ax25chat_usb as usb      # noqa: E402

# (kaartnummer, id, beschrijving, tweede regel, usb-apparaat van de kaart, [(by-id-naam, tty, usb-apparaat)])
SETS = [
    (1, "CODEC", "USB-Audio - USB Audio CODEC", "Burr-Brown from TI USB Audio CODEC at usb-3f980000.usb-1.1.2",
     "1-1.1.4", [("usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_IC-9700_12345678_A-if00-port0", "ttyUSB0", "1-1.1.1"),
                 ("usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_IC-9700_12345678_B-if00-port0", "ttyUSB1", "1-1.1.2")]),
    (2, "CODEC_1", "USB-Audio - USB Audio CODEC", "Burr-Brown from TI USB Audio CODEC at usb-3f980000.usb-1.2.2",
     "1-1.2.2", [("usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_IC-7300_03001234-if00-port0", "ttyUSB2", "1-1.2.1")]),
    (3, "CODEC_2", "USB-Audio - USB Audio CODEC", "Burr-Brown from TI USB Audio CODEC at usb-3f980000.usb-1.3.2",
     "1-1.3.2", [("usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_00A1B2C3-if00-port0", "ttyUSB3", "1-1.3.1"),
                 ("usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_00A1B2C3-if01-port0", "ttyUSB4", "1-1.3.1")]),
    (4, "Device", "USB-Audio - USB Audio Device", "C-Media Electronics Inc. USB Audio Device at usb-3f980000.usb-1.4.1",
     "1-1.4.1", [("usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_9a8b7c6d5e4f-if00-port0", "ttyUSB5", "1-1.4.2")]),
]


def maak_hardware(sets):
    for d in ("sys", "by-id", "dev"):
        shutil.rmtree(os.path.join(TMP, d), ignore_errors=True)
    sysd = os.path.join(TMP, "sys")
    regels = [" 0 [vc4hdmi        ]: vc4-hdmi - vc4-hdmi", "                      vc4-hdmi"]
    os.makedirs(os.path.join(sysd, "class", "sound", "card0"))      # HDMI: geen USB
    for nr, kid, tekst, meer, kapp, poorten in sets:
        regels += [f" {nr} [{kid:<15}]: {tekst}", f"                      {meer}"]
        apparaten = os.path.join(sysd, "devices", "platform", "soc", "usb1")
        kpad = os.path.join(apparaten, *_keten(kapp), f"{kapp}:1.0", "sound", f"card{nr}")
        os.makedirs(kpad)
        os.makedirs(os.path.join(sysd, "class", "sound", f"card{nr}"), exist_ok=True)
        os.symlink(kpad, os.path.join(sysd, "class", "sound", f"card{nr}", "device"))
        for naam, tty, papp in poorten:
            ppad = os.path.join(apparaten, *_keten(papp), f"{papp}:1.{tty[-1]}", tty)
            os.makedirs(ppad)
            os.makedirs(os.path.join(sysd, "class", "tty", tty), exist_ok=True)
            os.symlink(ppad, os.path.join(sysd, "class", "tty", tty, "device"))
            os.makedirs(os.path.join(TMP, "dev"), exist_ok=True)
            open(os.path.join(TMP, "dev", tty), "w").close()
            os.makedirs(os.path.join(TMP, "by-id"), exist_ok=True)
            os.symlink(os.path.join(TMP, "dev", tty), os.path.join(TMP, "by-id", naam))
    with open(os.path.join(TMP, "cards"), "w") as f:
        f.write("\n".join(regels) + "\n")


def _keten(app):
    """'1-1.3.2' -> ['1-1', '1-1.3', '1-1.3.2'] (de mappen in /sys/devices)."""
    delen = app.split(".")
    return [".".join(delen[:i]) for i in range(1, len(delen) + 1)]


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class TestUsb(unittest.TestCase):
    def setUp(self):
        maak_hardware(SETS)

    def test_groepen_per_hubje(self):
        g = {x["kaart"]: x for x in usb.inventaris()}
        self.assertNotIn("vc4hdmi", g)                                 # HDMI is geen USB-set
        self.assertEqual(g["CODEC"]["soort"], "icom")
        self.assertEqual(g["CODEC"]["naam"], "Icom IC-9700")
        self.assertEqual(len(g["CODEC"]["poorten"]), 2)
        self.assertEqual(g["CODEC_1"]["naam"], "Icom IC-7300")
        self.assertEqual(g["CODEC_2"]["soort"], "yaesu")
        self.assertEqual(g["Device"]["soort"], "digirig")

    def test_poorten_en_ptt(self):
        g = {x["kaart"]: x for x in usb.inventaris()}
        self.assertTrue(usb.ptt_poort(g["Device"]).endswith("9a8b7c6d5e4f-if00-port0"))
        self.assertTrue(usb.ptt_poort(g["CODEC_2"]).endswith("if01-port0"))         # SCU-17 poort B
        self.assertTrue(usb.ptt_poort(g["CODEC"]).endswith("_A-if00-port0"))        # IC-9700 poort A
        self.assertEqual(usb.cat_poorten(g["Device"]), [])                          # DigiRig: nooit CAT proberen
        self.assertEqual([s for _, s in usb.cat_poorten(g["CODEC_2"])], ["yaesu"])  # SCU-17 poort B niet

    def test_twee_digirigs(self):
        tweede = (5, "Device_1", "USB-Audio - USB Audio Device", "C-Media Electronics Inc. USB Audio Device",
                  "1-1.5.1", [("usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_0f1e2d3c4b5a-if00-port0", "ttyUSB6", "1-1.5.2")])
        maak_hardware(SETS + [tweede])
        g = {x["kaart"]: x for x in usb.inventaris()}
        self.assertTrue(usb.ptt_poort(g["Device"]).endswith("9a8b7c6d5e4f-if00-port0"))
        self.assertTrue(usb.ptt_poort(g["Device_1"]).endswith("0f1e2d3c4b5a-if00-port0"))

    def test_alleen_geluidskaart(self):
        maak_hardware([(1, "Device", "USB-Audio - USB PnP Sound Device", "C-Media", "1-1.2", [])])
        g = usb.inventaris()
        self.assertEqual([(x["kaart"], x["soort"]) for x in g], [("Device", "geluid")])


class TestRig(unittest.TestCase):
    def test_frequenties(self):
        self.assertEqual(len(rig.FREQ_2M), 9)
        self.assertEqual(rig.FREQ_2M[0], 144850000)
        self.assertEqual(rig.FREQ_2M[-1], 144950000)
        self.assertIn(rig.STANDAARD_FREQ, rig.FREQ_2M)
        self.assertEqual(rig.mhz(144862500), "144,8625 MHz")
        self.assertEqual(rig.mhz(0), "zelf ingesteld")

    def test_kandidaten(self):
        self.assertEqual(rig.kandidaten("usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_IC-7300_03001234-if00-port0"), [3073])
        self.assertEqual(rig.kandidaten("usb-Silicon_Labs_CP2102N_..._IC-9700_1_A-if00-port0"), [3081])
        self.assertEqual(rig.kandidaten("usb-Silicon_Labs_CP2102N_x-if00-port0", "digirig"), [])
        self.assertEqual(rig.kandidaten("usb-Silicon_Labs_CP2105_Dual_x-if01-port0"), [])
        self.assertIn(1041, rig.kandidaten("usb-Silicon_Labs_CP2105_Dual_x-if00-port0"))

    def test_ic7300_niet_op_2m(self):
        meld = rig.zet_set({"cat_model": 3073, "ptt_methode": "CAT", "cat_poort": "x"}, 144900000)
        self.assertTrue(meld and "kan niet op" in meld[0])


class TestRadio(unittest.TestCase):
    def setUp(self):
        maak_hardware(SETS)
        for f in (radio.RADIO_FILE, radio.STATION_FILE, radio.PROFIEL_FILE):
            if os.path.exists(f):
                os.remove(f)

    def test_direwolf_conf(self):
        t = radio.direwolf_tekst("PD3PAM-7", dict(radio.STANDAARD, geluidskaart="Device", ptt_methode="RTS",
                                                  ptt_poort="/dev/serial/by-id/x", txdelay_ms=400))
        self.assertIn("ADEVICE plughw:CARD=Device,DEV=0", t)
        self.assertIn("MYCALL PD3PAM-7", t)
        self.assertIn("PTT /dev/serial/by-id/x RTS", t)
        self.assertIn("TXDELAY 40", t)
        self.assertIn("MODEM 1200", t)
        self.assertIn("KISSPORT 8001", t)
        cat = radio.direwolf_tekst("PD3PAM", dict(radio.STANDAARD, geluidskaart="CODEC_1", ptt_methode="CAT",
                                                  cat_model=3073, cat_poort="/dev/x", modem="auto"))
        self.assertIn("PTT RIG 2 localhost:4532", cat)
        self.assertIn("MODEM 300", cat)                     # IC-7300: HF, dus 300 baud
        self.assertIn("# geen PTT", radio.direwolf_tekst("PD3PAM", dict(radio.STANDAARD, ptt_methode="VOX")))

    def test_voorstellen(self):
        groepen = usb.inventaris()
        pad9700 = [p for g in groepen for p, _ in g["poorten"] if "IC-9700" in p and "_A-" in p][0]
        vs = {v["geluidskaart"]: v for v in radio.voorstellen(groepen, [(pad9700, 3081, 115200, 144900000)])}
        self.assertEqual(vs["CODEC"]["ptt_methode"], "CAT")
        self.assertEqual(vs["CODEC"]["cat_mode"], "PKTFM")
        self.assertEqual(vs["CODEC_1"]["ptt_methode"], "RTS")         # IC-7300 antwoordde niet: RTS-voorstel
        self.assertEqual(vs["Device"]["ptt_methode"], "RTS")
        self.assertEqual(vs["Device"]["set_naam"], "DigiRig")

    def test_kies_en_profiel(self):
        groepen = usb.inventaris()
        v = [x for x in radio.voorstellen(groepen, []) if x["geluidskaart"] == "Device"][0]
        f = {k: str(v.get(k) or "") for k in radio.VOORSTEL_VELDEN}
        f["profiel"] = "UV-5R onderweg"
        fouten, _ = radio.kies_voorstel(f)
        self.assertEqual(fouten, [])
        self.assertIn("UV-5R onderweg", radio.profielen())
        self.assertEqual(radio.instellingen()["set_naam"], "UV-5R onderweg")
        with open(radio.DIREWOLF_CONF) as conf:
            self.assertIn("RTS", conf.read())
        fouten, let = radio.gebruik_profiel("UV-5R onderweg")
        self.assertEqual((fouten, let), ([], []))
        maak_hardware([])                                               # DigiRig losgehaald
        fouten, let = radio.gebruik_profiel("UV-5R onderweg")
        self.assertEqual(fouten, [])
        self.assertTrue(let)

    def test_station(self):
        fouten, _ = radio.verwerk_station({"roepnaam": "pd3pam-7", "frequentie": "144862500"})
        self.assertEqual(fouten, [])
        self.assertEqual(rig.doelfrequentie(), 144862500)
        fouten, _ = radio.verwerk_station({"roepnaam": "PD3PAM-7", "frequentie": "144800000"})   # APRS: niet in de lijst
        self.assertTrue(fouten)
        radio.verwerk_station({"roepnaam": "PD3PAM-7", "frequentie": "0"})
        self.assertIsNone(rig.doelfrequentie())
        fouten, _ = radio.verwerk_station({"roepnaam": "N0CALL", "frequentie": "0"})
        self.assertTrue(fouten)

    def test_meet_geluid(self):
        stil = array.array("h", [0] * 4800).tobytes()
        self.assertEqual(radio.advies_luister(*radio.meet_geluid(stil))[0], "fout")
        hard = array.array("h", [32767, -32768] * 2400).tobytes()
        self.assertEqual(radio.advies_luister(*radio.meet_geluid(hard))[0], "let")
        ruis = array.array("h", [(i * 7919) % 6000 - 3000 for i in range(4800)]).tobytes()
        self.assertEqual(radio.advies_luister(*radio.meet_geluid(ruis))[0], "ok")

    def test_html_radio(self):
        tekst = radio.html_radio("<input type=hidden name=csrf value=x>")
        for woord in ("Zoek mijn set", "Mijn sets", "Luistertest", "144,850 MHz", "Handmatig instellen"):
            self.assertIn(woord, tekst)


class TestAx25(unittest.TestCase):
    def test_ui_frame_met_pad(self):
        f = ax25.ax25_ui("PD3PAM-7", "CQ", "Hallo allemaal", ["WIDE1-1"])
        self.assertEqual(ax25.ax25_parse(f), ("PD3PAM-7", "CQ", b"Hallo allemaal"))
        k = ax25.kiss_encode(f + bytes([0xC0, 0xDB]))
        self.assertEqual(ax25.KissDecoder().feed(k), [f + bytes([0xC0, 0xDB])])


if __name__ == "__main__":
    unittest.main()
