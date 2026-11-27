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

Op Windows komen dezelfde gegevens uit PowerShell (Get-PnpDevice): de geluidskaarten (AudioEndpoint), de
COM-poorten en per apparaat het USB-pad (LocationPaths), zodat ook daar per hubje gegroepeerd wordt.
Een COM-poort krijgt een naam zoals onder /dev/serial/by-id, zodat de herkenning hetzelfde blijft.

Alleen standaard-Python. Paden zijn via omgevingsvariabelen te vervangen (voor de tests).
"""

import glob
import json
import os
import re
import subprocess
import sys
import threading
import time

ASOUND_CARDS = os.environ.get("AX25CHAT_ASOUND_CARDS", "/proc/asound/cards")
SERIAL_BY_ID = os.environ.get("AX25CHAT_SERIAL_BY_ID", "/dev/serial/by-id")
SYS = os.environ.get("AX25CHAT_SYS", "/sys")
WIN_JSON = os.environ.get("AX25CHAT_WIN_USB_JSON", "")     # tests: nagebootste PowerShell-uitvoer
WINDOWS = sys.platform == "win32" or bool(WIN_JSON)

USB_APPARAAT = re.compile(r"^\d+-\d+(\.\d+)*$")          # 1-1.3 (een apparaat; 1-1.3:1.0 is een interface)
CMEDIA = ("c-media", "cm108", "cm119", "usb audio device", "usb pnp sound")


def geluidskaarten(vers=False):
    """[(nummer, id, beschrijving)] uit /proc/asound/cards (Windows: de USB-geluidskaarten; vers=True vraagt opnieuw
    in plaats van de uitkomst van de laatste 30 s te gebruiken)."""
    if WINDOWS:
        return [(nr, kid, tekst) for nr, kid, tekst, _ in _windows(vers)[0]]
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


def seriele_poorten(vers=False):
    """[pad] uit /dev/serial/by-id (blijft gelijk na herstart, anders dan ttyUSB0). Windows: COM-poorten via USB."""
    if WINDOWS:
        return [p for p, _ in _windows(vers)[1]]
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


_NAMEN = {}          # Windows: "COM5" -> naam zoals onder /dev/serial/by-id


def naam(pad):
    """De herkenbare naam van een poort (Linux: de by-id-naam; Windows: een nagemaakte by-id-naam)."""
    return _NAMEN.get(pad) or os.path.basename(pad)


def korte_naam(pad):
    n = naam(pad)
    kort = re.sub(r"^usb-", "", n)
    kort = re.sub(r"_[0-9A-Fa-f]{6,}", "", kort)
    kort = re.sub(r"(-if0\d)?-port0$", "", kort)
    letter = poortletter(n)
    kort = kort + (f" [poort {letter}]" if letter else "")
    return f"{pad} · {kort}" if pad in _NAMEN else kort


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
    n = naam(pad).lower()
    if re.search(r"ic-?\d{3,4}|id-?\d{3,4}", n):
        return "icom"
    if "cp2105" in n:
        return "ptt" if "if01" in n else "yaesu"
    if ("cp2102" in n or "silicon_labs" in n) and any(c in kaartbeschrijving.lower() for c in CMEDIA):
        return "digirig"
    return "serieel"


def setnaam(pad):
    """'Icom IC-9700' uit de poortnaam, of ''."""
    m = re.search(r"(I[CD])-?(\d{3,4}[A-Z]?)", naam(pad), re.I)
    return f"Icom {m.group(1).upper()}-{m.group(2).upper()}" if m else ""


def inventaris():
    """Alle USB-sets, gegroepeerd per hubje. Geeft [{hub, kaart, kaart_tekst, poorten: [(pad, soort)], soort, naam}].

    soort van de groep: 'icom', 'yaesu', 'digirig', 'geluid' (alleen geluidskaart: VOX) of 'serieel' (alleen poort).
    """
    if WINDOWS:
        kaarten, poorten, hub = _windows(vers=True)
    else:
        kaarten = [(nr, kid, tekst, usb_kaart(nr)) for nr, kid, tekst in geluidskaarten()]
        kaarten = [k for k in kaarten if k[3]]                # alleen USB (niet de HDMI-/koptelefoonuitgang)
        poorten = [(p, usb_poort(p)) for p in seriele_poorten()]
        hub = hub_van
    groepen, gebruikt = [], set()
    for nr, kid, tekst, app in kaarten:
        h = hub(app)
        eigen = [p for p, pa in poorten if h and hub(pa) == h]
        gebruikt.update(eigen)
        groepen.append({"hub": h, "kaart": kid, "kaart_tekst": tekst,
                        "poorten": [(p, soort_poort(p, tekst)) for p in eigen]})
    for p, pa in poorten:
        if p not in gebruikt:
            groepen.append({"hub": hub(pa), "kaart": "", "kaart_tekst": "", "poorten": [(p, soort_poort(p))]})
    for g in groepen:
        soorten = [s for _, s in g["poorten"]]
        g["soort"] = next((s for s in ("icom", "yaesu", "digirig") if s in soorten),
                          "geluid" if not soorten else "serieel")
        g["naam"] = next((setnaam(p) for p, _ in g["poorten"] if setnaam(p)), "") or {
            "yaesu": "Yaesu met SCU-17 (of FT-991)", "digirig": "DigiRig (set zonder CAT)",
            "geluid": "USB-geluidskaart (PTT via VOX)", "icom": "Icom", "serieel": "USB-serieel apparaat"}[g["soort"]]
    return groepen


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

# Per apparaat (geluidskaart-ingang/-uitgang en COM-poort): naam, InstanceId, het USB-apparaat erboven en zijn
# USB-pad, bijv. PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(3)#USB(2). Alles in één keer, als JSON.
# Snel: de ouders worden per niveau in één keer opgevraagd (niet per apparaat), want elke Get-PnpDeviceProperty
# kost op Windows een flinke fractie van een seconde. Met veel apparaten duurde het per apparaat soms minuten.
PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$usbpat = '^USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}\\'
$dev = @(Get-PnpDevice -PresentOnly -Class AudioEndpoint, Ports)
$ouder = @{}
$todo = @($dev | ForEach-Object { [string]$_.InstanceId } | Where-Object { $_ -notmatch $usbpat })
for ($i = 0; $i -lt 8 -and $todo.Count -gt 0; $i++) {
  $volgende = @()
  foreach ($p in @(Get-PnpDeviceProperty -InstanceId $todo -KeyName DEVPKEY_Device_Parent)) {
    $o = [string]$p.Data
    $ouder[[string]$p.InstanceId] = $o
    if ($o -and $o -notmatch $usbpat -and -not $ouder.ContainsKey($o)) { $volgende += $o }
  }
  $todo = @($volgende | Select-Object -Unique)
}
$usb = @{}
foreach ($d in $dev) {
  $id = [string]$d.InstanceId
  for ($i = 0; $i -lt 9 -and $id -and $id -notmatch $usbpat; $i++) { $id = $ouder[$id] }
  if ($id -match $usbpat) { $usb[[string]$d.InstanceId] = $id } else { $usb[[string]$d.InstanceId] = '' }
}
$pad = @{}
$ids = @($usb.Values | Where-Object { $_ } | Select-Object -Unique)
if ($ids.Count -gt 0) {
  foreach ($p in @(Get-PnpDeviceProperty -InstanceId $ids -KeyName DEVPKEY_Device_LocationPaths)) {
    $pad[[string]$p.InstanceId] = [string]($p.Data | Select-Object -First 1)
  }
}
$uit = @()
foreach ($d in $dev) {
  $u = $usb[[string]$d.InstanceId]
  $uit += [pscustomobject]@{ klasse = [string]$d.Class; naam = [string]$d.FriendlyName; id = [string]$d.InstanceId;
                             usb = [string]$u; pad = $(if ($u) { [string]$pad[$u] } else { '' }) }
}
ConvertTo-Json -InputObject @($uit) -Compress
"""

_WIN_BEWAAR = 30        # seconden dat de uitkomst geldig blijft (een pagina vraagt hem meerdere keren op)
_WIN_LAATST = [0.0, None]
_WIN_SLOT = threading.Lock()
_WIN_KAARTEN = {}     # geluidskaart (tekst tussen haakjes) -> {"in": volledige naam, "uit": volledige naam}


def _windows_ruw(vers=False):
    """De apparaten volgens PowerShell. Bewaard voor _WIN_BEWAAR seconden; vers=True vraagt opnieuw (Zoek mijn set).
    Vragen er twee tegelijk, dan wacht de tweede op de eerste in plaats van zelf PowerShell te starten."""
    with _WIN_SLOT:
        if not vers and _WIN_LAATST[1] is not None and time.time() - _WIN_LAATST[0] < _WIN_BEWAAR:
            return _WIN_LAATST[1]
        data = _windows_ps()
        if data is None:
            return _WIN_LAATST[1] or []                     # mislukt: de vorige uitkomst, en niets bewaren
        _WIN_LAATST[:] = [time.time(), data]
        return data


def win_vooraf():
    """Bij het starten op de achtergrond alvast opvragen, zodat de eerste keer Radio openen niet hoeft te wachten."""
    if WINDOWS:
        threading.Thread(target=_windows_ruw, daemon=True).start()


def _windows_ps():
    if WIN_JSON:
        with open(WIN_JSON, encoding="utf-8") as f:
            return json.load(f)
    """None als PowerShell faalde (dan wordt er niets bewaard en vraagt de volgende keer opnieuw)."""
    begin = time.time()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_SCRIPT],
                           capture_output=True, text=True, timeout=90,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError) as fout:
        print(f"USB-apparaten opvragen lukte niet ({time.time() - begin:.0f} s): {fout}", flush=True)
        return None
    data = data if isinstance(data, list) else [data]
    print(f"USB-apparaten opgevraagd: {len(data)} in {time.time() - begin:.1f} s", flush=True)
    return data


def win_hub(pad):
    """Het hubje boven een USB-pad, of '' als het apparaat direct aan de PC hangt (net als hub_van op Linux)."""
    if "#" not in (pad or ""):
        return ""
    ouder = pad.rsplit("#", 1)[0]
    return ouder if ouder.rsplit("#", 1)[-1].startswith("USB(") else ""


def _tussen_haakjes(naam_):
    m = re.search(r"\((.+)\)\s*$", naam_ or "")
    return m.group(1).strip() if m else (naam_ or "").strip()


def _byid_naam(x, usb_id):
    """Een naam zoals onder /dev/serial/by-id, zodat soort_poort, poortletter en setnaam hetzelfde werken.
    USB\\VID_10C4&PID_EA60\\IC-9700 12345678 A  ->  usb-Silicon_Labs_CP2102_IC-9700_12345678_A-if00-port0"""
    eigen = x.get("id", "")
    m = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", eigen + usb_id, re.I)
    vidpid = (m.group(1) + ":" + m.group(2)).upper() if m else ""
    chip = {"10C4:EA60": "Silicon_Labs_CP2102", "10C4:EA70": "Silicon_Labs_CP2105", "10C4:EA71": "Silicon_Labs_CP2108",
            "0403:6001": "FTDI_FT232R", "0403:6015": "FTDI_FT231X", "067B:2303": "Prolific_PL2303"}.get(vidpid)
    if not chip:
        chip = re.sub(r"\W+", "_", re.sub(r"\s*\(COM\d+\)\s*$", "", x.get("naam", ""))).strip("_") or "Serieel"
    serie = (usb_id or eigen).split("\\")[-1]
    serie = "" if "&" in serie else re.sub(r"\s+", "_", serie.strip())   # met & = door Windows verzonnen
    mi = re.search(r"&MI_(\d\d)", eigen, re.I)
    return f"usb-{chip}{'_' + serie if serie else ''}-if{mi.group(1) if mi else '00'}-port0"


def _windows(vers=False):
    """(kaarten [(nr, id, tekst, usb-pad)], poorten [(COMx, usb-pad)], hub-functie) voor inventaris()."""
    kaarten, poorten = {}, []
    ruw = _windows_ruw(vers)
    _NAMEN.clear()
    _WIN_KAARTEN.clear()
    for x in ruw:
        if not x.get("usb"):
            continue                                        # niet via USB (ingebouwde geluidskaart, COM1)
        if x.get("klasse") == "Ports":
            m = re.search(r"\((COM\d+)\)", x.get("naam", ""))
            if m:
                _NAMEN[m.group(1)] = _byid_naam(x, x["usb"])
                poorten.append((m.group(1), x.get("pad", "")))
        elif x.get("klasse") == "AudioEndpoint":
            kid = _tussen_haakjes(x.get("naam"))
            richting = "in" if re.search(r"\{0\.0\.1\.", x.get("id", "")) else "uit"
            kaarten.setdefault(x["usb"], {"id": kid, "pad": x.get("pad", "")})
            _WIN_KAARTEN.setdefault(kid, {})[richting] = x.get("naam", "")
    lijst = [(i, k["id"], k["id"], k["pad"]) for i, k in enumerate(kaarten.values())]
    return lijst, sorted(poorten, key=lambda p: int(p[0][3:])), win_hub


def win_adevice(kaart):
    """ADEVICE-regel voor Direwolf op Windows. Direwolf zoekt een stukje tekst in de naam van het geluidsapparaat
    (max. 31 tekens), apart voor ingang en uitgang. Zonder gegevens: de tekst tussen haakjes."""
    if not _WIN_KAARTEN and kaart:
        try:
            _windows()
        except Exception:
            pass
    k = _WIN_KAARTEN.get(kaart, {})
    ingang = (k.get("in") or kaart or "0")[:31].rstrip()
    uitgang = (k.get("uit") or kaart or "0")[:31].rstrip()
    return f'ADEVICE "{ingang}" "{uitgang}"'


def ptt_poort(groep):
    """De poort voor PTT via RTS: DigiRig = zijn CP2102; SCU-17 = poort B; Icom = poort A (USB SEND)."""
    poorten = groep["poorten"]
    for soort in ("digirig", "ptt"):
        for p, s in poorten:
            if s == soort:
                return p
    for p, s in poorten:
        if s == "icom" and poortletter(naam(p)) in ("A", ""):
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
