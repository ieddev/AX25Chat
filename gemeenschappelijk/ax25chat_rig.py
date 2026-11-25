"""
ax25chat_rig.py - besturing van de set via hamlib (rigctld). Overgenomen uit Noodnet (noodnet_rig.py).

  rigctld (dienst ax25chat-rigctld) is de enige die de CAT-poort opent. Direwolf (PTT RIG 2
  localhost:4532) en de webpagina praten via TCP met rigctld.

  - frequentie: tabblad Radio, onderdeel Station (of "zelf instellen" voor sets zonder CAT)
  - set instellen: frequentie, datamode (PKTFM / PKTUSB), zendvermogen
  - bewaker: zet de set terug als iemand eraan draait (niet tijdens zenden)
  - Zoek mijn set: probeert bekende modellen/snelheden op de USB-poorten

Alleen standaard-Python.
"""

import html as _html
import json
import os
import re
import socket
import subprocess
import threading
import time

MAP = os.environ.get("AX25CHAT_MAP") or os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(MAP, "rigctld.env")
LOG_FILE = os.path.join(MAP, "rig_log.json")
STATION_FILE = os.path.join(MAP, "station.json")
RADIO_FILE = os.path.join(MAP, "radio_instellingen.json")
RIGCTL = os.environ.get("AX25CHAT_RIGCTL", "rigctl")
HOST, POORT = "127.0.0.1", int(os.environ.get("AX25CHAT_RIGCTLD_POORT", "4532"))

# 2 m: 144,850 - 144,950 MHz op het 12,5 kHz-raster (afgesproken 25-11-2026). 70 cm en HF volgen later.
FREQ_2M = list(range(144850000, 144950001, 12500))
APRS_FREQ = 144800000                     # APRS: om te luisteren en APRS-berichten (bijv. met APRSdroid)
STANDAARD_FREQ = 144900000
PAKKET_MODES = {"PKTFM", "FM-D", "FMD", "DATA-FM", "FM-DATA", "PKTUSB", "PKTLSB", "USB-D", "LSB-D"}
# Keuze bij Station (naast de frequentie). "" = automatisch: FM-D op 2 m en 70 cm, USB-D op HF.
MODES = [("", "Automatisch (FM-D, op HF USB-D)"), ("PKTFM", "FM-D (FM-packet, bijv. 1200 baud)"),
         ("PKTUSB", "USB-D (SSB-packet)"), ("PKTLSB", "LSB-D"), ("FM", "FM (set zonder datamode)")]
_FAMILIE = {"PKTFM": "PKTFM", "FM-D": "PKTFM", "FMD": "PKTFM", "DATA-FM": "PKTFM", "FM-DATA": "PKTFM",
            "PKTUSB": "PKTUSB", "USB-D": "PKTUSB", "PKTLSB": "PKTLSB", "LSB-D": "PKTLSB", "FM": "FM"}
MODE_NAAM = {"PKTFM": "FM-D", "PKTUSB": "USB-D", "PKTLSB": "LSB-D", "FM": "FM"}
_GEEN_DATAMODE = set()                    # sets (hamlib-model) die PKTFM weigerden; daar is FM goed
HF_GRENS = 30000000                       # onder 30 MHz: HF, modem 300 baud, mode PKTUSB

# (hamlib-nummer, merk, model, snelheden om te proberen). Gecontroleerd met Hamlib 4.5 (rigctl -l).
MODELLEN = [
    (3081, "Icom", "IC-9700", [115200, 19200, 9600]),
    (3073, "Icom", "IC-7300", [115200, 19200, 9600]),
    (3085, "Icom", "IC-705", [115200, 19200, 9600]),
    (3070, "Icom", "IC-7100", [19200, 115200, 9600]),
    (3068, "Icom", "IC-9100", [19200, 115200, 9600]),
    (3044, "Icom", "IC-910", [19200, 9600]),
    (3071, "Icom", "ID-5100", [19200, 9600]),
    (1035, "Yaesu", "FT-991 / FT-991A", [38400, 9600, 4800]),
    (1041, "Yaesu", "FT-818", [38400, 9600, 4800]),
    (1020, "Yaesu", "FT-817", [38400, 9600, 4800]),
    (1022, "Yaesu", "FT-857", [38400, 9600, 4800]),
    (1043, "Yaesu", "FT-897D", [38400, 9600, 4800]),
    (1023, "Yaesu", "FT-897", [38400, 9600, 4800]),
    (1001, "Yaesu", "FT-847", [57600, 9600, 4800]),
    (2014, "Kenwood", "TS-2000", [57600, 9600, 38400]),
    (2034, "Kenwood", "TM-D710", [57600, 9600]),
    (2035, "Kenwood", "TM-V71", [57600, 9600]),
    (2042, "Kenwood", "TH-D74", [9600, 57600]),
    (2007, "Kenwood", "TS-790", [4800, 9600]),
]
MODEL_NAAM = {m: f"{merk} {naam}" for m, merk, naam, _ in MODELLEN}
SNELHEDEN = [4800, 9600, 19200, 38400, 57600, 115200]
ALLEEN_HF = {3073}                        # sets zonder 2 m (IC-7300: HF + 6 m)


# ---------------------------------------------------------------------------
# Instellingen
# ---------------------------------------------------------------------------

def _lees(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def doelfrequentie():
    """Frequentie in Hz uit station.json, of None als de gebruiker de set zelf instelt."""
    d = _lees(STATION_FILE)
    if isinstance(d, dict) and "frequentie" in d:
        try:
            return int(d["frequentie"]) or None
        except (TypeError, ValueError):
            return STANDAARD_FREQ
    return STANDAARD_FREQ


def mhz(hz):
    """144925000 -> '144,925 MHz'; 144937500 -> '144,9375 MHz' (12,5 kHz-raster)."""
    if not hz:
        return "zelf ingesteld"
    t = f"{hz / 1e6:.4f}"
    if t.endswith("0"):
        t = t[:-1]
    return t.replace(".", ",") + " MHz"


# Amateurbanden (Hz) waarin je zelf frequenties mag toevoegen (Mijn frequenties)
BANDEN = [(1810000, 2000000), (3500000, 3800000), (7000000, 7200000), (10100000, 10150000), (14000000, 14350000),
          (18068000, 18168000), (21000000, 21450000), (24890000, 24990000), (28000000, 29700000),
          (50000000, 52000000), (144000000, 146000000), (430000000, 440000000)]
SNELHEDEN = [("auto", "Automatisch (HF 300, anders 1200)"), ("1200", "1200 baud"), ("300", "300 baud"),
             ("9600", "9600 baud")]


def eigen_frequenties():
    """Zelf toegevoegde frequenties: [{'hz', 'mode', 'baud', 'naam'}], gesorteerd op frequentie."""
    d = _lees(STATION_FILE)
    lijst = d.get("eigen") if isinstance(d, dict) else None
    uit = []
    for x in lijst or []:
        try:
            uit.append({"hz": int(x["hz"]), "mode": x.get("mode") if x.get("mode") in MODE_NAAM else "",
                        "baud": x.get("baud") if x.get("baud") in dict(SNELHEDEN) else "auto",
                        "naam": str(x.get("naam") or "")[:30]})
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return sorted(uit, key=lambda x: x["hz"])


def eigen(hz):
    """De eigen frequentie met deze waarde, of None."""
    return next((x for x in eigen_frequenties() if x["hz"] == hz), None)


def lees_mhz(tekst):
    """'144,775' of '7.0449' -> Hz (hoogstens 4 cijfers achter de komma), of None."""
    t = (tekst or "").strip().lower().replace("mhz", "").strip().replace(",", ".")
    if not re.fullmatch(r"\d{1,3}(\.\d{1,4})?", t):
        return None
    heel, _, deel = t.partition(".")
    return int(heel) * 1000000 + int((deel + "0000")[:4]) * 100


def in_band(hz):
    return any(a <= hz <= b for a, b in BANDEN)


def frequentie_keuzes():
    return [APRS_FREQ] + list(FREQ_2M) + [x["hz"] for x in eigen_frequenties()]


def eigen_tekst(x):
    """'144,775 MHz · USB-D · PD4R'"""
    delen = [mhz(x["hz"])]
    if x["mode"]:
        delen.append(MODE_NAAM[x["mode"]])
    if x["baud"] != "auto":
        delen.append(x["baud"] + " baud")
    if x["naam"]:
        delen.append(x["naam"])
    return " · ".join(delen)


def html_frequentie_keuze(huidig, naam="frequentie"):
    """Keuzelijst: de vaste 2 m-kanalen, of 'zelf instellen' (sets zonder CAT, of een andere band)."""
    opties = (f'<option value="0"{" selected" if not huidig else ""}>Zelf instellen op de set '
              f'(geen CAT, of een andere band)</option>')
    opties += '<optgroup label="2 m">'
    for k in [APRS_FREQ] + list(FREQ_2M):
        opties += (f'<option value="{k}"{" selected" if k == huidig else ""}>'
                   f'{_html.escape(mhz(k))}{" (standaard)" if k == STANDAARD_FREQ else " (APRS)" if k == APRS_FREQ else ""}</option>')
    opties += '</optgroup>'
    mijn = [x for x in eigen_frequenties() if x["hz"] not in FREQ_2M and x["hz"] != APRS_FREQ]
    if mijn:
        opties += '<optgroup label="Mijn frequenties">' + "".join(
            f'<option value="{x["hz"]}"{" selected" if x["hz"] == huidig else ""}>{_html.escape(eigen_tekst(x))}</option>'
            for x in mijn) + '</optgroup>'
    let = ""
    if huidig and huidig not in frequentie_keuzes():
        opties += f'<option value="{int(huidig)}" selected>{_html.escape(mhz(huidig))} (eerder ingesteld)</option>'
        let = ('<p class="melding let" style="margin:6px 0">De ingestelde frequentie staat niet (meer) in de lijst. '
               'Kies er een en sla op, of voeg hem toe bij Mijn frequenties.</p>')
    return f'{let}<select name="{naam}">{opties}</select>'


def is_hf(hz):
    return bool(hz) and hz < HF_GRENS


def doelmode(r):
    """De mode waarin de set moet staan: de keuze bij Station, of automatisch op basis van de frequentie."""
    d = _lees(STATION_FILE)
    gekozen = d.get("mode") if isinstance(d, dict) else ""
    if gekozen in MODE_NAAM:
        return gekozen
    doel = doelfrequentie()
    x = eigen(doel) if doel else None
    if x and x["mode"]:
        return x["mode"]
    if doel:
        return "PKTUSB" if is_hf(doel) else "PKTFM"
    return r.get("cat_mode") or "PKTFM"


def mode_goed(r, mode):
    """Staat de set in de gekozen mode? (FM-D en USB-D zijn niet hetzelfde: de bewaker zet het terug.)"""
    nu, doel = _FAMILIE.get((mode or "").upper()), doelmode(r)
    if nu == doel:
        return True
    return doel == "PKTFM" and nu == "FM" and int(r.get("cat_model") or 0) in _GEEN_DATAMODE


def cat_actief(r):
    return r.get("ptt_methode") == "CAT" and r.get("cat_model") and r.get("cat_poort")


def schrijf_env(r):
    """rigctld.env voor de dienst ax25chat-rigctld; zonder CAT wordt het bestand verwijderd (dienst wacht dan)."""
    if cat_actief(r):
        tmp = ENV_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"MODEL={int(r['cat_model'])}\nPOORT={r['cat_poort']}\nBAUD={int(r.get('cat_baud') or 19200)}\n")
        os.replace(tmp, ENV_FILE)
    elif os.path.exists(ENV_FILE):
        os.remove(ENV_FILE)


# ---------------------------------------------------------------------------
# Praten met rigctld
# ---------------------------------------------------------------------------

def opdracht(cmd, timeout=4):
    """Stuurt één opdracht in het uitgebreide protocol (+). Geeft (ok, [regels])."""
    try:
        with socket.create_connection((HOST, POORT), timeout=timeout) as s:
            s.sendall(("+" + cmd + "\n").encode())
            data = b""
            eind = time.time() + timeout
            while time.time() < eind:
                try:
                    x = s.recv(4096)
                except socket.timeout:
                    break
                if not x:
                    break
                data += x
                if re.search(rb"RPRT -?\d+", data):
                    break
    except OSError as fout:
        return False, [f"geen verbinding met rigctld: {fout}"]
    regels = data.decode(errors="replace").strip().splitlines()
    m = re.search(r"RPRT (-?\d+)", regels[-1]) if regels else None
    return bool(m and m.group(1) == "0"), regels[1:-1] if m else regels


def _waarde(regels, sleutel=None):
    for r in regels:
        if sleutel and r.startswith(sleutel + ":"):
            return r.split(":", 1)[1].strip()
    return regels[0].strip() if regels and not sleutel else None


def status():
    """Live gegevens van de set. Geeft dict; 'fout' als rigctld niet antwoordt."""
    ok, f = opdracht("f")
    if not ok:
        return {"fout": "; ".join(f) or "geen antwoord van de set"}
    uit = {}
    try:
        uit["frequentie"] = int(float(_waarde(f, "Frequency")))
    except (TypeError, ValueError):
        return {"fout": "onverwacht antwoord: " + " ".join(f)}
    ok, m = opdracht("m")
    if ok:
        uit["mode"] = _waarde(m, "Mode")
    ok, t = opdracht("t")
    if ok:
        uit["ptt"] = _waarde(t, "PTT") == "1"
    for niveau, sleutel in (("STRENGTH", "s"), ("RFPOWER", "vermogen")):
        ok, v = opdracht("l " + niveau)
        if ok and v:
            try:
                uit[sleutel] = float(v[-1])
            except ValueError:
                pass
    if uit.get("vermogen") is not None and not 0 <= uit["vermogen"] <= 1:
        uit.pop("vermogen")                                  # bijv. FT-817/818: kan het vermogen niet uitlezen
    if uit.get("vermogen") is not None:                     # 0..1 -> watt (hamlib kent het maximum per set)
        ok, v = opdracht(f"\\power2mW {uit['vermogen']:.4f} {uit['frequentie']} {uit.get('mode') or 'FM'}")
        w = _waarde(v, "Power mW") if ok else None
        try:
            uit["watt"] = float(w) / 1000 if w is not None else None
        except ValueError:
            pass
    return uit


def watt_tekst(st):
    if st.get("watt"):
        return f"{st['watt']:g} W"
    return "niet uit te lezen" if st.get("vermogen") is None else f"{int(round(st['vermogen'] * 100))}%"


def s_meter(db):
    """hamlib STRENGTH (dB t.o.v. S9) -> 'S7' of 'S9+10'."""
    if db is None:
        return "–"
    if db >= 0:
        return f"S9+{int(round(db / 10) * 10)}" if db >= 5 else "S9"
    return f"S{max(0, 9 + int(round(db / 6)))}"


def zet_set(r, freq=None):
    """Zet frequentie (als die er is), datamode en (optioneel) vermogen. Geeft [meldingen]."""
    freq = freq if freq is not None else doelfrequentie()
    meld = []
    ok, t = opdracht("t")
    if ok and _waarde(t, "PTT") == "1":
        return ["De set zendt nu; probeer het zo opnieuw."]
    if freq and int(r.get("cat_model") or 0) in ALLEEN_HF and not is_hf(freq):
        return [f"De {MODEL_NAAM.get(int(r['cat_model']), 'set')} kan niet op {mhz(freq)}. Kies bij Station "
                f"'Zelf instellen op de set' en zet de set zelf op je HF-frequentie."]
    if freq:
        ok, uit = opdracht(f"F {freq}")
        if not ok:
            return ["Frequentie zetten lukte niet: " + " ".join(uit)]
    mode = doelmode(r)
    ok, uit = opdracht(f"M {mode} 0")
    if not ok and mode == "PKTFM":
        ok, uit = opdracht("M FM 0")
        if ok:
            _GEEN_DATAMODE.add(int(r.get("cat_model") or 0))
            meld.append("Deze set kent geen datamode via CAT; FM gekozen. Controleer of het geluid van USB komt.")
    if not ok:
        meld.append("Mode zetten lukte niet: " + " ".join(uit))
    watt = r.get("cat_watt")
    if watt and freq:
        deel = None
        for m in (mode, "FM"):                               # niet elke set kent de datamode in zijn zendbereik
            ok, uit = opdracht(f"\\mW2power {int(float(watt) * 1000)} {freq} {m}")
            try:
                deel = float(_waarde(uit, "Power [0.0..1.0]")) if ok else None
            except (TypeError, ValueError):
                deel = None
            if deel is not None:
                break
        if deel is None:
            meld.append(f"{watt:g} W instellen lukte niet: meer dan deze set kan, of de set kent geen omrekening naar watt. "
                        f"Vul minder in, of stel het vermogen op de set zelf in.")
        else:
            if deel >= 0.999:
                meld.append(f"{watt:g} W is het maximum van deze set (of meer); vermogen op maximaal gezet.")
            ok, uit = opdracht(f"L RFPOWER {min(deel, 1.0):.3f}")
            if not ok:
                meld.append("Vermogen zetten lukte niet (niet elke set kan dat via CAT).")
    return meld


def log(tekst):
    regels = _lees(LOG_FILE) or []
    regels.append([time.strftime("%d-%m %H:%M:%S"), tekst])
    tmp = LOG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(regels[-30:], f, ensure_ascii=False)
    os.replace(tmp, LOG_FILE)


def logregels(n=8):
    return (_lees(LOG_FILE) or [])[-n:][::-1]


def bewaak(r):
    """Staat de set niet (meer) op de ingestelde frequentie en datamode? Dan terugzetten. Geeft tekst of None."""
    doel = doelfrequentie()
    if not cat_actief(r) or not doel:
        return None
    st = status()
    if "fout" in st or st.get("ptt"):
        return None
    if abs(st["frequentie"] - doel) <= 100 and mode_goed(r, st.get("mode")):
        return None
    was = f"{mhz(st['frequentie'])} {st.get('mode') or '?'}"
    meld = zet_set(r, doel)
    tekst = f"Set stond op {was}; teruggezet naar {mhz(doel)}" + (f" ({'; '.join(meld)})" if meld else "")
    log(tekst)
    return tekst


def start_bewaker(lees_instellingen, schrijf_log=None, interval=60):
    """Achtergrondtaak in de webserver: elke minuut controleren."""
    def lus():
        time.sleep(20)
        while True:
            try:
                uit = bewaak(lees_instellingen())
                if uit and schrijf_log:
                    schrijf_log(uit)
            except Exception as fout:        # nooit de webserver laten vallen
                if schrijf_log:
                    schrijf_log(f"bewaker set: {fout}")
            time.sleep(interval)
    threading.Thread(target=lus, daemon=True, name="rig-bewaker").start()


# ---------------------------------------------------------------------------
# Zoek mijn set (CAT-deel; het herkennen van USB-apparaten staat in ax25chat_usb.py)
# ---------------------------------------------------------------------------

def kandidaten(poortnaam, soort=""):
    """Modellen om te proberen voor een USB-poort, op basis van de naam en (indien bekend) de soort aansluiting."""
    n = poortnaam.lower()
    if soort in ("digirig", "ptt"):
        return []          # DigiRig: alleen PTT (RTS), geen CAT. SCU-17 poort B: PTT-poort. Nooit CAT proberen.
    if "cp2105" in n and "if01" in n:
        return []          # Yaesu SCU-17 / FT-991 poort B: dat is de PTT-poort (RTS = zenden). Nooit openen.
    for m, merk, naam, _ in MODELLEN:
        kern = naam.split()[0].lower()
        if kern in n or kern.replace("-", "") in n:
            return [m]
    if "cp2105" in n:                                     # Yaesu SCU-17 (FT-817/818) of FT-991 (Enhanced COM)
        return [1041, 1020, 1035, 1022, 1023]
    if "silicon_labs" in n or "cp210" in n:               # Icom-sets met ingebouwde USB
        return [3081, 3073, 3085, 3070, 3068, 3044]
    return [m for m, *_ in MODELLEN]


def probeer(model, poort, baud, timeout=4):
    """rigctl -m model -r poort -s baud f -> frequentie in Hz of None."""
    try:
        r = subprocess.run([RIGCTL, "-m", str(model), "-r", poort, "-s", str(baud),
                            "-C", "timeout=500,retry=0,rts_state=OFF,dtr_state=OFF", "f"],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        hz = int(float(r.stdout.strip().splitlines()[0]))
    except (ValueError, IndexError):
        return None
    return hz if 1000000 <= hz <= 10000000000 else None


def zoek(poorten, max_seconden=90):
    """poorten: [(pad, soort)]. Geeft (gevonden [(pad, model, baud, freq)], [meldingen])."""
    gevonden, meld, begin = [], [], time.time()
    snelheden = {m: b for m, _, _, b in MODELLEN}
    for pad, soort in poorten:
        for model in kandidaten(os.path.basename(pad), soort):
            for baud in snelheden.get(model, [19200, 9600]):
                if time.time() - begin > max_seconden:
                    meld.append("Zoeken gestopt na anderhalve minuut; kies de set eventueel zelf in de lijst.")
                    return gevonden, meld
                hz = probeer(model, pad, baud)
                if hz:
                    gevonden.append((pad, model, baud, hz))
                    break
            if gevonden and gevonden[-1][0] == pad:
                break
    return gevonden, meld


def wacht_en_zet(max_s=25):
    """Door ax25chat-direwolf.service bij het starten: bij CAT wachten tot rigctld antwoordt, dan de set instellen."""
    r = _lees(RADIO_FILE) or {}
    if not cat_actief(r):
        return "geen CAT"
    eind = time.time() + max_s
    while time.time() < eind:
        ok, _ = opdracht("f", timeout=2)
        if ok:
            meld = zet_set(r)
            doel = doelfrequentie()
            tekst = (f"Set ingesteld op {mhz(doel)}" if doel else "Set in datamode gezet (frequentie stel je zelf in)") + \
                (f" ({'; '.join(meld)})" if meld else "")
            log(tekst)
            return tekst
        time.sleep(1)
    log("rigctld antwoordt niet: is de set aan en klopt de CAT-poort?")
    return "rigctld antwoordt niet"


if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        print(status())
    if "--wacht" in sys.argv:
        print(wacht_en_zet())
