"""
ax25chat_usb.py - USB-apparaten van de Pi vinden en per set groeperen (nieuw in AX25Chat).

Een set aan de Pi bestaat bijna altijd uit een USB-geluidskaart en een of twee seriële poorten
achter één klein USB-hubje in de set of kabel:

  Icom IC-9700      hub met USB Audio CODEC + twee CP2102N (poort A en B)
  Icom IC-7300      hub met USB Audio CODEC + CP2102 (één poort)
  Yaesu SCU-17      hub met USB Audio CODEC + CP2105 (if00 = CAT, if01 = PTT)
  DigiRig Mobile    hub met C-Media CM108 (geluid) + CP2102N (alleen PTT via RTS, geen CAT)

Door te kijken welke geluidskaart en welke poort aan hetzelfde hubje hangen (via /sys), weet de Pi
welke geluidskaart bij welke poort hoort, en kan hij een DigiRig herkennen: een CP2102 naast een
C-Media-geluidskaart, zonder sets-naam. Die hoeft dan niet op alle CAT-modellen te worden geprobeerd.

Alleen standaard-Python. Paden zijn via omgevingsvariabelen te vervangen (voor de tests).
"""

import glob
import os
import re

ASOUND_CARDS = os.environ.get("AX25CHAT_ASOUND_CARDS", "/proc/asound/cards")
SERIAL_BY_ID = os.environ.get("AX25CHAT_SERIAL_BY_ID", "/dev/serial/by-id")
SYS = os.environ.get("AX25CHAT_SYS", "/sys")

USB_APPARAAT = re.compile(r"^\d+-\d+(\.\d+)*$")          # 1-1.3 (een apparaat; 1-1.3:1.0 is een interface)
CMEDIA = ("c-media", "cm108", "cm119", "usb audio device", "usb pnp sound")


def geluidskaarten():
    """[(nummer, id, beschrijving)] uit /proc/asound/cards."""
    uit = []
    try:
        with open(ASOUND_CARDS, encoding="utf-8") as f:
            regels = f.read().splitlines()
    except OSError:
        return uit
    for i, regel in enumerate(regels):
        m = re.match(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(.*)$", regel)
        if m:
            meer = regels[i + 1].strip() if i + 1 < len(regels) else ""
            uit.append((int(m.group(1)), m.group(2), (m.group(3).strip() + " " + meer).strip()))
    return uit


def seriele_poorten():
    """[pad] uit /dev/serial/by-id (blijft gelijk na herstart, anders dan ttyUSB0)."""
    return sorted(glob.glob(os.path.join(SERIAL_BY_ID, "*")))


def poortletter(naam):
    """'A' of 'B' voor sets/kabels met twee USB-poorten.
    Icom IC-9700: twee CP2102N-chips, naam eindigt op _A-if00 / _B-if00.
    Yaesu SCU-17: een CP2105 met if00 (A) en if01 (B)."""
    m = re.search(r"_([AB])-if0\d", naam)
    if m:
        return m.group(1)
    if "-if00" in naam and "cp2105" in naam.lower():
        return "A"
    if "-if01" in naam:
        return "B"
    return ""


def korte_naam(pad):
    naam = os.path.basename(pad)
    kort = re.sub(r"^usb-", "", naam)
    kort = re.sub(r"_[0-9A-Fa-f]{6,}", "", kort)
    kort = re.sub(r"(-if0\d)?-port0$", "", kort)
    letter = poortletter(naam)
    return kort + (f" [poort {letter}]" if letter else "")


def _usb_apparaat(sysfs_pad):
    """Het USB-apparaat ('1-1.3') waar dit sysfs-pad onder valt, of ''."""
    try:
        echt = os.path.realpath(sysfs_pad)
    except OSError:
        return ""
    for deel in reversed(echt.split(os.sep)):
        if USB_APPARAAT.match(deel):
            return deel
    return ""


def hub_van(apparaat):
    """'1-1.3.2' -> '1-1.3' (het hubje waar het aan hangt). Een apparaat direct aan de Pi: geen hub."""
    return apparaat.rsplit(".", 1)[0] if "." in apparaat else ""


def usb_kaart(nummer):
    return _usb_apparaat(os.path.join(SYS, "class", "sound", f"card{nummer}", "device"))


def usb_poort(pad):
    try:
        tty = os.path.basename(os.path.realpath(pad))
    except OSError:
        return ""
    return _usb_apparaat(os.path.join(SYS, "class", "tty", tty, "device"))


def soort_poort(pad, kaartbeschrijving=""):
    """Wat voor poort is dit? 'icom', 'yaesu', 'ptt' (SCU-17 poort B), 'digirig' of 'serieel'."""
    n = os.path.basename(pad).lower()
    if re.search(r"ic-?\d{3,4}|id-?\d{3,4}", n):
        return "icom"
    if "cp2105" in n:
        return "ptt" if "if01" in n else "yaesu"
    if ("cp2102" in n or "silicon_labs" in n) and any(c in kaartbeschrijving.lower() for c in CMEDIA):
        return "digirig"
    return "serieel"


def setnaam(pad):
    """'Icom IC-9700' uit de poortnaam, of ''."""
    m = re.search(r"(I[CD])-?(\d{3,4}[A-Z]?)", os.path.basename(pad), re.I)
    return f"Icom {m.group(1).upper()}-{m.group(2).upper()}" if m else ""


def inventaris():
    """Alle USB-sets, gegroepeerd per hubje. Geeft [{hub, kaart, kaart_tekst, poorten: [(pad, soort)], soort, naam}].

    soort van de groep: 'icom', 'yaesu', 'digirig', 'geluid' (alleen geluidskaart: VOX) of 'serieel' (alleen poort).
    """
    kaarten = [(nr, kid, tekst, usb_kaart(nr)) for nr, kid, tekst in geluidskaarten()]
    kaarten = [k for k in kaarten if k[3]]                    # alleen USB (niet de HDMI-/koptelefoonuitgang)
    poorten = [(p, usb_poort(p)) for p in seriele_poorten()]
    groepen, gebruikt = [], set()
    for nr, kid, tekst, app in kaarten:
        hub = hub_van(app)
        eigen = [p for p, pa in poorten if hub and hub_van(pa) == hub]
        gebruikt.update(eigen)
        groepen.append({"hub": hub, "kaart": kid, "kaart_tekst": tekst,
                        "poorten": [(p, soort_poort(p, tekst)) for p in eigen]})
    for p, pa in poorten:
        if p not in gebruikt:
            groepen.append({"hub": hub_van(pa), "kaart": "", "kaart_tekst": "", "poorten": [(p, soort_poort(p))]})
    for g in groepen:
        soorten = [s for _, s in g["poorten"]]
        g["soort"] = next((s for s in ("icom", "yaesu", "digirig") if s in soorten),
                          "geluid" if not soorten else "serieel")
        g["naam"] = next((setnaam(p) for p, _ in g["poorten"] if setnaam(p)), "") or {
            "yaesu": "Yaesu met SCU-17 (of FT-991)", "digirig": "DigiRig (set zonder CAT)",
            "geluid": "USB-geluidskaart (PTT via VOX)", "icom": "Icom", "serieel": "USB-serieel apparaat"}[g["soort"]]
    return groepen


def ptt_poort(groep):
    """De poort voor PTT via RTS: DigiRig = zijn CP2102; SCU-17 = poort B; Icom = poort A (USB SEND)."""
    poorten = groep["poorten"]
    for soort in ("digirig", "ptt"):
        for p, s in poorten:
            if s == soort:
                return p
    for p, s in poorten:
        if s == "icom" and poortletter(os.path.basename(p)) in ("A", ""):
            return p
    return poorten[0][0] if poorten else ""


def cat_poorten(groep):
    """Poorten om CAT op te proberen (nooit de DigiRig of de PTT-poort van een SCU-17)."""
    return [(p, s) for p, s in groep["poorten"] if s not in ("digirig", "ptt")]


if __name__ == "__main__":
    for g in inventaris():
        print(f"{g['naam']}: geluidskaart {g['kaart'] or '-'} ({g['kaart_tekst']}), hub {g['hub'] or '-'}")
        for p, s in g["poorten"]:
            print(f"   {s:8} {p}")
