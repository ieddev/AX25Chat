"""
Tests voor AX25Chat op Windows, zonder Windows: Zoek mijn set met nagebootste PowerShell-uitvoer
(Get-PnpDevice) van Gerts sets: IC-9700, DigiRig en een Yaesu met SCU-17, plus een ingebouwde geluidskaart en COM1.

    python3 -m unittest discover -s tests
"""

import importlib
import json
import os
import sys
import tempfile
import unittest

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "gemeenschappelijk"))

R = "PCIROOT(0)#PCI(1400)#USBROOT(0)"
APPARATEN = [
    # IC-9700: hubje op USB(3) met twee CP2102N (poort A en B) en de USB Audio CODEC
    {"klasse": "Ports", "naam": "Silicon Labs CP210x USB to UART Bridge (COM5)",
     "id": "USB\\VID_10C4&PID_EA60\\IC-9700 12345678 A", "usb": "USB\\VID_10C4&PID_EA60\\IC-9700 12345678 A",
     "pad": R + "#USB(3)#USB(1)"},
    {"klasse": "Ports", "naam": "Silicon Labs CP210x USB to UART Bridge (COM6)",
     "id": "USB\\VID_10C4&PID_EA60\\IC-9700 12345678 B", "usb": "USB\\VID_10C4&PID_EA60\\IC-9700 12345678 B",
     "pad": R + "#USB(3)#USB(2)"},
    {"klasse": "AudioEndpoint", "naam": "Microfoon (USB Audio CODEC)", "id": "SWD\\MMDEVAPI\\{0.0.1.00000000}.{a1}",
     "usb": "USB\\VID_08BB&PID_2901\\5&1&0&4", "pad": R + "#USB(3)#USB(4)"},
    {"klasse": "AudioEndpoint", "naam": "Luidsprekers (USB Audio CODEC)", "id": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{a2}",
     "usb": "USB\\VID_08BB&PID_2901\\5&1&0&4", "pad": R + "#USB(3)#USB(4)"},
    # DigiRig: hubje op USB(5) met CP2102 (PTT) en een C-Media-geluidskaart
    {"klasse": "Ports", "naam": "Silicon Labs CP210x USB to UART Bridge (COM11)",
     "id": "USB\\VID_10C4&PID_EA60\\b2c3d4e5", "usb": "USB\\VID_10C4&PID_EA60\\b2c3d4e5", "pad": R + "#USB(5)#USB(1)"},
    {"klasse": "AudioEndpoint", "naam": "Microfoon (2- USB PnP Sound Device)", "id": "SWD\\MMDEVAPI\\{0.0.1.00000000}.{b1}",
     "usb": "USB\\VID_0D8C&PID_0012\\6&2&0&2", "pad": R + "#USB(5)#USB(2)"},
    {"klasse": "AudioEndpoint", "naam": "Luidsprekers (2- USB PnP Sound Device)", "id": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{b2}",
     "usb": "USB\\VID_0D8C&PID_0012\\6&2&0&2", "pad": R + "#USB(5)#USB(2)"},
    # SCU-17: hubje op USB(6) met CP2105 (if00 = CAT, if01 = PTT) en een USB Audio CODEC
    {"klasse": "Ports", "naam": "Silicon Labs Dual CP2105 USB to UART Bridge: Enhanced COM Port (COM7)",
     "id": "USB\\VID_10C4&PID_EA70&MI_00\\7&3&0&0000", "usb": "USB\\VID_10C4&PID_EA70\\00A1B2C3", "pad": R + "#USB(6)#USB(1)"},
    {"klasse": "Ports", "naam": "Silicon Labs Dual CP2105 USB to UART Bridge: Standard COM Port (COM8)",
     "id": "USB\\VID_10C4&PID_EA70&MI_01\\7&3&0&0001", "usb": "USB\\VID_10C4&PID_EA70\\00A1B2C3", "pad": R + "#USB(6)#USB(1)"},
    {"klasse": "AudioEndpoint", "naam": "Microfoon (3- USB Audio CODEC)", "id": "SWD\\MMDEVAPI\\{0.0.1.00000000}.{c1}",
     "usb": "USB\\VID_08BB&PID_2901\\6&3&0&2", "pad": R + "#USB(6)#USB(2)"},
    {"klasse": "AudioEndpoint", "naam": "Luidsprekers (3- USB Audio CODEC)", "id": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{c2}",
     "usb": "USB\\VID_08BB&PID_2901\\6&3&0&2", "pad": R + "#USB(6)#USB(2)"},
    # Niet via USB: de ingebouwde geluidskaart en COM1
    {"klasse": "AudioEndpoint", "naam": "Luidsprekers (Realtek(R) Audio)", "id": "SWD\\MMDEVAPI\\{0.0.0.00000000}.{d}",
     "usb": "", "pad": ""},
    {"klasse": "Ports", "naam": "Communicatiepoort (COM1)", "id": "ACPI\\PNP0501\\0", "usb": "", "pad": ""},
]


class TestWindowsUsb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.json = os.path.join(tempfile.mkdtemp(prefix="ax25chat-win-"), "pnp.json")
        with open(cls.json, "w", encoding="utf-8") as f:
            json.dump(APPARATEN, f)
        os.environ["AX25CHAT_WIN_USB_JSON"] = cls.json
        import ax25chat_usb
        cls.usb = importlib.reload(ax25chat_usb)

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("AX25CHAT_WIN_USB_JSON", None)
        importlib.reload(cls.usb)

    def groep(self, soort):
        return next(g for g in self.usb.inventaris() if g["soort"] == soort)

    def test_drie_sets_gevonden(self):
        groepen = self.usb.inventaris()
        self.assertEqual(sorted(g["soort"] for g in groepen), ["digirig", "icom", "yaesu"])

    def test_ic9700(self):
        g = self.groep("icom")
        self.assertEqual(g["naam"], "Icom IC-9700")
        self.assertEqual(g["kaart"], "USB Audio CODEC")
        self.assertEqual([p for p, _ in g["poorten"]], ["COM5", "COM6"])
        self.assertEqual(self.usb.ptt_poort(g), "COM5")              # poort A
        self.assertIn("[poort B]", self.usb.korte_naam("COM6"))

    def test_digirig(self):
        g = self.groep("digirig")
        self.assertEqual(g["kaart"], "2- USB PnP Sound Device")
        self.assertEqual(self.usb.ptt_poort(g), "COM11")
        self.assertEqual(self.usb.cat_poorten(g), [])                # DigiRig: nooit CAT proberen

    def test_scu17(self):
        g = self.groep("yaesu")
        self.assertEqual(dict(g["poorten"]), {"COM7": "yaesu", "COM8": "ptt"})
        self.assertEqual(self.usb.ptt_poort(g), "COM8")
        self.assertEqual([p for p, _ in self.usb.cat_poorten(g)], ["COM7"])

    def test_adevice(self):
        self.usb.inventaris()
        self.assertEqual(self.usb.win_adevice("2- USB PnP Sound Device"),
                         'ADEVICE "Microfoon (2- USB PnP Sound Dev" "Luidsprekers (2- USB PnP Sound"')   # max. 31 tekens
        self.assertEqual(self.usb.win_adevice("USB Audio CODEC"),
                         'ADEVICE "Microfoon (USB Audio CODEC)" "Luidsprekers (USB Audio CODEC)"')

    def test_lijsten_voor_handmatig(self):
        self.assertEqual(self.usb.seriele_poorten(), ["COM5", "COM6", "COM7", "COM8", "COM11"])
        self.assertEqual([k for _, k, _ in self.usb.geluidskaarten()],
                         ["USB Audio CODEC", "2- USB PnP Sound Device", "3- USB Audio CODEC"])

    def test_icom_cat_zendt_via_rts_op_poort_b(self):
        import ax25chat_radio as radio
        v = radio.voorstellen(self.usb.inventaris(), [("COM5", 3081, 19200, 144900000)])
        icom = next(x for x in v if x["set_naam"].startswith("Icom"))
        self.assertEqual((icom["ptt_methode"], icom["cat_poort"], icom["ptt_poort"]), ("CAT", "COM5", "COM6"))
        conf = radio.direwolf_tekst("PD3PAM", icom)
        self.assertIn("PTT COM6 RTS", conf)
        self.assertNotIn("PTT RIG", conf)                         # Direwolf voor Windows heeft geen Hamlib

    def test_hub(self):
        self.assertEqual(self.usb.win_hub(R + "#USB(3)#USB(2)"), R + "#USB(3)")
        self.assertEqual(self.usb.win_hub(R + "#USB(3)"), "")        # direct aan de PC: geen hubje


class TestWindowsNiveau(unittest.TestCase):
    def test_niveau_uit_log(self):
        import ax25chat_radio as radio
        log = ("ADEVICE0: Sample rate approx. 44.1 k, 0 errors, receive audio level CH0 12\n"
               "ADEVICE0: Sample rate approx. 44.1 k, 0 errors, receive audio level CH0 48\n")
        self.assertEqual(radio.niveau_uit_log(log), 48)
        self.assertIsNone(radio.niveau_uit_log("niets"))
        self.assertEqual(radio.advies_niveau(48)[0], "ok")
        self.assertEqual(radio.advies_niveau(2)[0], "fout")
        self.assertEqual(radio.advies_niveau(15)[0], "let")


if __name__ == "__main__":
    unittest.main()
