"""
ax25chat_radio.py - de set aan de Pi: instellingen, profielen, direwolf.conf, Zoek mijn set,
luistertest, geluidsniveaus en testuitzending. Plus de html van het tabblad Radio.

Grotendeels overgenomen uit Noodnet (noodnet_radio.py). Nieuw in AX25Chat:
  - Zoek mijn set vindt ook sets zonder CAT (DigiRig, alleen een USB-geluidskaart) en koppelt
    de geluidskaart aan de juiste poort via het USB-hubje (ax25chat_usb.py)
  - profielen: elke gevonden set bewaren, daarna wisselen met één tik
  - modem 1200 of 300 baud (HF), TXDELAY instelbaar (bijv. ruimer voor een Baofeng)
  - luistertest: komt er geluid van de set binnen, ook zonder dat er packets zijn

Alleen standaard-Python. Instellingen staan in de map van het script (~/ax25chat).
"""

import array
import html
import json
import math
import os
import re
import subprocess
import sys
import time

import ax25chat_rig as rig
import ax25chat_usb as usb

e = html.escape

MAP = rig.MAP
RADIO_FILE = rig.RADIO_FILE
STATION_FILE = rig.STATION_FILE
PROFIEL_FILE = os.path.join(MAP, "profielen.json")
DIREWOLF_CONF = os.path.join(MAP, "direwolf.conf")
HOTSPOT_FILE = os.path.join(MAP, "hotspot.json")
SUDO = os.environ.get("AX25CHAT_SUDO", "sudo")
SYSTEMCTL = os.environ.get("AX25CHAT_SYSTEMCTL", "systemctl")
JOURNALCTL = os.environ.get("AX25CHAT_JOURNALCTL", "journalctl")
AMIXER = os.environ.get("AX25CHAT_AMIXER", "amixer")
ARECORD = os.environ.get("AX25CHAT_ARECORD", "arecord")

DW = "ax25chat-direwolf"
RIGD = "ax25chat-rigctld"
DIENSTEN = [(RIGD, "CAT-besturing van de set (rigctld)"), (DW, "Direwolf (modem)"), ("ax25chat-web", "Webserver")]

STANDAARD = {"set_naam": "", "geluidskaart": "", "ptt_methode": "VOX", "ptt_poort": "",
             "cat_model": 0, "cat_poort": "", "cat_baud": 0, "cat_watt": None, "cat_mode": "PKTFM",
             "modem": "auto", "txdelay_ms": 300}
METHODES = [("CAT", "CAT: de Pi bestuurt de set (Icom, Yaesu)"), ("RTS", "RTS: alleen PTT (DigiRig, SCU-17 poort B)"),
            ("DTR", "DTR: alleen PTT"), ("VOX", "VOX van de set (geen PTT-aansluiting)")]
ROEPNAAM_RE = re.compile(r"^[A-Z0-9]{3,6}(-([0-9]|1[0-5]))?$")


# ---------------------------------------------------------------------------
# Bestanden
# ---------------------------------------------------------------------------

def lees(pad, standaard=None):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standaard


def schrijf(pad, data):
    tmp = pad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, pad)


def instellingen():
    r = dict(STANDAARD)
    r.update(lees(RADIO_FILE, {}) or {})
    return r


def station():
    s = {"roepnaam": "N0CALL", "frequentie": rig.STANDAARD_FREQ, "pad": ""}
    s.update(lees(STATION_FILE, {}) or {})
    s["roepnaam"] = schoon_call(s.get("roepnaam")) or "N0CALL"       # oude instelling 'PD3PAM-0' wordt 'PD3PAM'
    return s


def schoon_call(call):
    """Hoofdletters, zonder spaties en zonder '-0' (SSID 0 is hetzelfde als geen SSID, zie ax25chat_agw)."""
    call = str(call or "").strip().upper().replace(" ", "")
    return call[:-2] if call.endswith("-0") else call


def reservekopie(pad):
    if os.path.exists(pad):
        kopie = pad + ".bak"
        with open(pad, "rb") as a, open(kopie, "wb") as b:
            b.write(a.read())


def _uit(cmd, timeout=5):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def dienst(actie, naam):
    """systemctl restart/stop/start van een eigen dienst (sudo zonder wachtwoord, zie installeer.sh). Geeft (ok, fout)."""
    if naam not in [d for d, _ in DIENSTEN] or actie not in ("restart", "stop", "start"):
        return False, "onbekende dienst"
    try:
        r = subprocess.run([SUDO, "-n", SYSTEMCTL, actie, naam], capture_output=True, text=True, timeout=30)
        return (True, "") if r.returncode == 0 else (False, (r.stderr or r.stdout).strip()[:200])
    except Exception as fout:
        return False, str(fout)


def dienst_status(naam):
    return _uit([SYSTEMCTL, "is-active", naam]).strip() or "onbekend"


# ---------------------------------------------------------------------------
# direwolf.conf
# ---------------------------------------------------------------------------

def modem(r, doel=None):
    """1200, 300 of 9600 baud: zoals gekozen bij de set, anders die van de eigen frequentie, anders op basis
    van de frequentie (HF = 300)."""
    if str(r.get("modem")) in ("1200", "300", "9600"):
        return int(r["modem"])
    doel = rig.doelfrequentie() if doel is None else doel
    x = rig.eigen(doel) if doel else None
    if x and x["baud"] != "auto":
        return int(x["baud"])
    return 300 if rig.is_hf(doel) or int(r.get("cat_model") or 0) in rig.ALLEEN_HF else 1200


def direwolf_tekst(roepnaam, r):
    kaart = r.get("geluidskaart") or "Device"
    if rig.cat_actief(r):
        ptt = "# PTT via CAT: rigctld (dienst ax25chat-rigctld)\nPTT RIG 2 localhost:4532"
    elif r.get("ptt_poort") and r.get("ptt_methode") in ("RTS", "DTR"):
        ptt = f"PTT {r['ptt_poort']} {r['ptt_methode']}"
    else:
        ptt = "# geen PTT ingesteld (VOX van de set)"
    try:
        txdelay = max(5, min(100, round(int(r.get("txdelay_ms") or 300) / 10)))
    except (TypeError, ValueError):
        txdelay = 30
    return f"""# Gemaakt door AX25Chat ({time.strftime('%Y-%m-%d %H:%M')}), tabblad Radio.
# Met de hand wijzigen heeft geen zin: dit bestand wordt overschreven.
# Set: {r.get('set_naam') or '-'}
ADEVICE plughw:CARD={kaart},DEV=0
ACHANNELS 1
CHANNEL 0
MYCALL {schoon_call(roepnaam) or 'N0CALL'}
MODEM {modem(r)}
{ptt}
TXDELAY {txdelay}
TXTAIL 10
DWAIT 0
SLOTTIME 10
PERSIST 63
KISSPORT 8001
AGWPORT 8000
# Verbinden (BBS, node) met AX.25 v2.0 (SABM). Veel nodes (BPQ) antwoorden op v2.2 (SABME) met FRMR,
# en sommige versies van Direwolf vallen dan niet goed terug.
MAXV22 0
"""


def direwolf_met_agw():
    """Is direwolf.conf bij de tijd: AGW-poort (voor BBS'en, connected mode) aan en verbinden met AX.25 v2.0?"""
    try:
        with open(DIREWOLF_CONF, encoding="utf-8") as f:
            t = f.read()
        return "\nAGWPORT 8000" in t and "\nMAXV22 0" in t and not re.search(r"\nMYCALL \S+-0\n", t)
    except OSError:
        return True                    # nog geen direwolf.conf: die wordt straks met AGW gemaakt


def maak_direwolf(roepnaam, r):
    reservekopie(DIREWOLF_CONF)
    tmp = DIREWOLF_CONF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(direwolf_tekst(roepnaam, r))
    os.replace(tmp, DIREWOLF_CONF)


def pas_toe(r, roepnaam=None, met_rig=True):
    """Instellingen opslaan, rigctld.env en direwolf.conf maken, diensten herstarten. Geeft [fouten].
    met_rig=False: rigctld laten draaien (alleen Station gewijzigd), zodat de set meteen ingesteld kan worden."""
    schrijf(RADIO_FILE, r)
    rig.schrijf_env(r)
    maak_direwolf(roepnaam or station()["roepnaam"], r)
    mis = []
    for d in ((RIGD, DW) if met_rig else (DW,)):
        ok, fout = dienst("restart", d)
        if not ok:
            mis.append(f"{d} herstarten lukte niet: {fout}")
    return mis


# ---------------------------------------------------------------------------
# Profielen
# ---------------------------------------------------------------------------

def profielen():
    p = lees(PROFIEL_FILE, {}) or {}
    return p if isinstance(p, dict) else {}


def bewaar_profiel(naam, r):
    naam = re.sub(r"\s+", " ", str(naam or "")).strip()[:40]
    if not naam:
        return "Geef het profiel een naam."
    p = profielen()
    p[naam] = {k: r.get(k) for k in STANDAARD}
    p[naam]["set_naam"] = naam
    schrijf(PROFIEL_FILE, p)
    return ""


def verwijder_profiel(naam):
    p = profielen()
    if p.pop(naam, None) is not None:
        schrijf(PROFIEL_FILE, p)


def gebruik_profiel(naam):
    """Zet een bewaard profiel actief. Geeft (fouten, waarschuwingen)."""
    p = profielen().get(naam)
    if not p:
        return ["Dit profiel bestaat niet (meer)."], []
    r = dict(STANDAARD)
    r.update(p)
    let = []
    kaarten = [k for _, k, _ in usb.geluidskaarten()]
    poorten = usb.seriele_poorten()
    if r.get("geluidskaart") and r["geluidskaart"] not in kaarten:
        let.append(f"Geluidskaart {r['geluidskaart']} is nu niet aangesloten. Zit de set aan de Pi en staat hij aan?")
    for sleutel in ("cat_poort", "ptt_poort"):
        if r.get(sleutel) and r["ptt_methode"] != "VOX" and r[sleutel] not in poorten and \
                (sleutel == "ptt_poort" or rig.cat_actief(r)):
            let.append(f"Poort {usb.korte_naam(r[sleutel])} is nu niet aangesloten.")
    return pas_toe(r), let


# ---------------------------------------------------------------------------
# Geluidsniveaus (overgenomen uit Noodnet)
# ---------------------------------------------------------------------------

def mixer(kaart):
    """Regelaars van de geluidskaart: {"zend": (naam, %), "ontvang": (naam, %)} (alleen wat er is)."""
    if not kaart:
        return {}
    tekst = _uit([AMIXER, "-c", kaart, "scontents"])
    regelaars, huidig = [], None
    for regel in tekst.splitlines():
        m = re.match(r"Simple mixer control '(.+)',(\d+)", regel)
        if m:
            huidig = {"naam": m.group(1), "caps": "", "p": None, "c": None}
            regelaars.append(huidig)
        elif huidig is not None:
            if "Capabilities:" in regel:
                huidig["caps"] = regel
            pct = re.search(r"\[(\d+)%\]", regel)
            if pct and ":" in regel:
                soort = "p" if "Playback" in regel else ("c" if "Capture" in regel else None)
                if soort and huidig[soort] is None:
                    huidig[soort] = int(pct.group(1))

    def kies(cap, soort, voorkeur):
        kandidaten = [r for r in regelaars if re.search(rf"\b{cap}\b", r["caps"]) and r[soort] is not None]
        kandidaten.sort(key=lambda r: next((i for i, v in enumerate(voorkeur) if v in r["naam"].lower()), 99))
        return (kandidaten[0]["naam"], kandidaten[0][soort]) if kandidaten else None

    uit = {}
    z = kies("pvolume", "p", ["speaker", "pcm", "headphone", "master"])
    o = kies("cvolume", "c", ["mic", "capture", "line"])
    if z:
        uit["zend"] = z
    if o:
        uit["ontvang"] = o
    return uit


def zet_niveaus(r=None):
    """Zet de opgeslagen niveaus op de geluidskaart (ook bij het starten van Direwolf). Geeft [fouten]."""
    r = r or instellingen()
    kaart = r.get("geluidskaart")
    m = mixer(kaart)
    fouten = []
    for sleutel, extra in (("zend", ["unmute"]), ("ontvang", ["cap"])):
        waarde = r.get(f"niveau_{sleutel}")
        if waarde is None or sleutel not in m:
            continue
        try:
            subprocess.run([AMIXER, "-q", "-c", kaart, "sset", m[sleutel][0], f"{int(waarde)}%"] + extra,
                           check=True, capture_output=True, text=True, timeout=5)
        except Exception as fout:
            fouten.append(f"Niveau {sleutel} zetten lukte niet: {getattr(fout, 'stderr', '') or fout}")
    return fouten


_GEHOORD = {}          # uren -> (tijd, uitkomst): journalctl over 24 uur duurt op een Pi Zero seconden


def gehoorde_stations(uren=24, log=None):
    """Stations die Direwolf de laatste uren hoorde, uit 'CALL audio level = N(...)'.
    Geeft [{call, laatst (epoch), niveau, niveaus, aantal}], nieuwste eerst. Een halve minuut onthouden."""
    if log is None:
        oud = _GEHOORD.get(uren)
        if oud and time.time() - oud[0] < 30:
            return oud[1]
        uit = gehoorde_stations(uren, _uit([JOURNALCTL, "-u", DW, "--no-pager", "-o", "short-iso", "--since", f"-{int(uren)}h"], timeout=10))
        _GEHOORD[uren] = (time.time(), uit)
        return uit
    st = {}
    for regel in log.splitlines():
        kop, _, bericht = regel.partition(": ")
        m = re.search(r"^(?:\[[^\]]*\]\s*)?([A-Za-z0-9]{1,6}(?:-\d{1,2})?)\s+audio level = (\d+)", bericht.strip())
        if not m:
            continue
        try:
            t = time.mktime(time.strptime(kop.split(" ", 1)[0][:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            t = 0
        call, niv = m.group(1).upper(), int(m.group(2))
        x = st.setdefault(call, {"call": call, "laatst": 0, "niveau": niv, "niveaus": [], "aantal": 0})
        x["aantal"] += 1
        x["niveaus"] = (x["niveaus"] + [niv])[-5:]
        if t >= x["laatst"]:
            x["laatst"], x["niveau"] = t, niv
    return sorted(st.values(), key=lambda x: -x["laatst"])


def advies_kort(niveau):
    if niveau < 15:
        return "te zacht"
    if niveau > 100:
        return "te hard"
    return "goed" if 30 <= niveau <= 70 else "bruikbaar"


# ---------------------------------------------------------------------------
# Luistertest (nieuw): komt er geluid van de set binnen?
# ---------------------------------------------------------------------------

def meet_geluid(data):
    """Ruwe 16-bit mono samples -> (piek in %, gemiddeld in dBFS)."""
    a = array.array("h")
    a.frombytes(data[:len(data) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    if not a:
        return 0.0, -120.0
    piek = max(abs(x) for x in a) / 32768 * 100
    rms = math.sqrt(sum(x * x for x in a) / len(a)) / 32768
    return round(piek, 1), round(20 * math.log10(rms), 1) if rms > 0 else -120.0


def advies_luister(piek, dbfs):
    if piek < 0.5:
        return "fout", ("Er komt (bijna) geen geluid binnen. Staat de ruisonderdrukking (squelch) even open, het volume "
                        "van de set omhoog, en klopt de geluidskaart? Zet het ontvangstniveau hieronder hoger.")
    if piek >= 99:
        return "let", ("Het geluid is overstuurd (de piek raakt het maximum). Zet het ontvangstniveau hieronder lager, "
                       "of het volume van de set (bij een Baofeng/GM-340 met DigiRig).")
    if dbfs < -45:
        return "let", "Er komt geluid binnen, maar heel zacht. Zet het ontvangstniveau wat hoger."
    return "ok", "Er komt geluid van de set binnen. Goed zo; zet de ruisonderdrukking (squelch) daarna weer terug."


def luistertest(r=None, seconden=5):
    """Direwolf even stoppen (die houdt de geluidskaart bezet), opnemen, meten, Direwolf weer starten.
    Geeft (soort, tekst, piek, dbfs)."""
    r = r or instellingen()
    kaart = r.get("geluidskaart")
    if not kaart:
        return "fout", "Kies eerst de geluidskaart van de set.", None, None
    dienst("stop", DW)
    try:
        p = subprocess.run([ARECORD, "-q", "-D", f"plughw:CARD={kaart},DEV=0", "-f", "S16_LE", "-r", "48000",
                            "-c", "1", "-t", "raw", "-d", str(int(seconden))],
                           capture_output=True, timeout=seconden + 10)
        data, fout = p.stdout, p.stderr.decode(errors="replace").strip()
    except Exception as x:
        data, fout = b"", str(x)
    finally:
        dienst("start", DW)
    if not data:
        return "fout", f"Opnemen lukte niet ({fout[:200] or 'geen geluid'}). Klopt de geluidskaart?", None, None
    piek, dbfs = meet_geluid(data)
    soort, tekst = advies_luister(piek, dbfs)
    return soort, tekst, piek, dbfs


# ---------------------------------------------------------------------------
# Testuitzending (overgenomen uit Noodnet)
# ---------------------------------------------------------------------------

def testuitzending(roepnaam, lang=False, wacht=None):
    """Laat Direwolf een kort testbericht uitzenden (test PTT en geluid in één keer). Geeft (gelukt, [regels])."""
    import socket
    import ax25chat_ax25 as ax25
    if not roepnaam or roepnaam.upper().startswith("N0CALL"):
        return False, ["Stel eerst je eigen roepnaam in (onderdeel Station)."]
    if dienst_status(DW) != "active":
        return False, ["Direwolf draait niet. Kies de geluidskaart en sla op."]
    tekst = f"AX25Chat test {roepnaam.upper()}"
    frames = [tekst] if not lang else [f"{tekst} ({i}/4) " + "-" * 150 for i in range(1, 5)]
    begin = time.time()
    try:
        with socket.create_connection(ax25.DIREWOLF, timeout=5) as s:
            for t in frames:
                s.sendall(ax25.kiss_encode(ax25.ax25_ui(roepnaam, "TEST", t)))
            time.sleep(0.5)
    except (OSError, ValueError) as fout:
        return False, [f"Geen verbinding met Direwolf (poort 8001): {fout}"]
    time.sleep(wacht if wacht is not None else (7 if lang else 3))
    log = _uit([JOURNALCTL, "-u", DW, "--no-pager", "-o", "cat",
                "--since", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(begin - 1))], timeout=10)
    regels = [x.strip() for x in log.splitlines() if ">TEST" in x or "PTT" in x or "rror" in x]
    return True, regels[-8:]


# ---------------------------------------------------------------------------
# Zoek mijn set
# ---------------------------------------------------------------------------

def voorstellen(groepen, gevonden):
    """Per USB-groep een voorstel voor de instellingen. gevonden: [(pad, model, baud, hz)] van rig.zoek."""
    uit = []
    for g in groepen:
        cat = next((x for x in gevonden if x[0] in [p for p, _ in g["poorten"]]), None)
        basis = {"geluidskaart": g["kaart"], "ptt_poort": "", "cat_model": 0, "cat_poort": "", "cat_baud": 0}
        if cat:
            pad, model, baud, hz = cat
            hf = rig.is_hf(hz) or model in rig.ALLEEN_HF
            v = dict(basis, set_naam=rig.MODEL_NAAM.get(model, g["naam"]), ptt_methode="CAT", cat_model=model,
                     cat_poort=pad, cat_baud=baud, cat_mode="PKTUSB" if hf else "PKTFM", modem="300" if hf else "1200",
                     _uitleg=f"CAT gevonden op {baud} baud, de set staat op {rig.mhz(hz)}.")
        elif g["soort"] == "digirig":
            v = dict(basis, set_naam="DigiRig", ptt_methode="RTS", ptt_poort=usb.ptt_poort(g), modem="1200",
                     _uitleg="DigiRig: PTT via RTS, geen CAT. Stel de frequentie (het kanaal) op de set zelf in.")
        elif g["soort"] in ("icom", "yaesu"):
            v = dict(basis, set_naam=g["naam"], ptt_methode="RTS", ptt_poort=usb.ptt_poort(g), modem="auto",
                     _uitleg="De set is herkend, maar antwoordt niet op CAT. Staat hij aan? Voorstel: PTT via RTS. "
                             "Zoek later nog eens om CAT te gebruiken.")
        elif g["soort"] == "geluid":
            v = dict(basis, set_naam=g["naam"], ptt_methode="VOX", modem="1200",
                     _uitleg="Alleen een USB-geluidskaart, geen PTT-aansluiting: zet VOX aan op de set.")
        else:
            continue
        if not v["geluidskaart"]:
            v["_uitleg"] += " Let op: geen geluidskaart bij deze poort gevonden; kies die hieronder bij Handmatig."
        uit.append(v)
    return uit


def zoek_mijn_set(roepnaam):
    """Inventaris + CAT proberen. Geeft (voorstellen, [meldingen])."""
    groepen = usb.inventaris()
    if not groepen:
        return [], ["Geen USB-geluidskaart of USB-serieel apparaat gevonden. Is de set (of DigiRig) aangesloten en aan?"]
    poorten = [x for g in groepen for x in usb.cat_poorten(g)]
    gevonden, meld = [], []
    if poorten:
        r = instellingen()
        # poorten vrijmaken: rigctld laten wachten en Direwolf zonder PTT starten
        if os.path.exists(rig.ENV_FILE):
            os.replace(rig.ENV_FILE, rig.ENV_FILE + ".zoek")
        maak_direwolf(roepnaam, dict(r, ptt_methode="VOX", ptt_poort=""))
        dienst("restart", RIGD)
        dienst("restart", DW)
        time.sleep(2)
        try:
            gevonden, meld = rig.zoek(poorten)
        finally:
            if os.path.exists(rig.ENV_FILE + ".zoek"):
                os.replace(rig.ENV_FILE + ".zoek", rig.ENV_FILE)
            maak_direwolf(roepnaam, r)
            dienst("restart", RIGD)
            dienst("restart", DW)
    return voorstellen(groepen, gevonden), meld


VOORSTEL_VELDEN = ("set_naam", "geluidskaart", "ptt_methode", "ptt_poort", "cat_model", "cat_poort", "cat_baud",
                   "cat_mode", "modem")


def html_voorstellen(vs, meld, verborgen):
    if not vs:
        return ("<div class='melding fout'>Geen set gevonden. Staat de set aan en zit de USB-kabel erin? Bij een Icom: "
                "<i>CI-V USB Port</i> op 'Unlink from [REMOTE]' en het CI-V-adres op standaard.</div>" +
                "".join(f"<div class='melding let'>{e(m)}</div>" for m in meld))
    rijen = ""
    for v in vs:
        velden = "".join(f"<input type='hidden' name='{k}' value='{e(str(v.get(k) or ''))}'>" for k in VOORSTEL_VELDEN)
        details = [f"geluidskaart {v['geluidskaart'] or '?'}"]
        if v["ptt_methode"] == "CAT":
            details.append(f"CAT {usb.korte_naam(v['cat_poort'])}")
        elif v["ptt_methode"] in ("RTS", "DTR"):
            details.append(f"PTT {v['ptt_methode']} op {usb.korte_naam(v['ptt_poort'])}")
        else:
            details.append("PTT via VOX")
        details.append("modem " + ("automatisch" if v["modem"] == "auto" else v["modem"] + " baud"))
        rijen += (f"<section><h2>{e(v['set_naam'])}</h2><p class='uitleg'>{e(v['_uitleg'])}</p>"
                  f"<p class='mono'>{e(' · '.join(details))}</p>"
                  f"<form method='post' action='/set_kies' style='margin:0'>{verborgen}{velden}"
                  f"<label>Naam voor dit profiel <small>bijv. 'UV-5R onderweg'</small></label>"
                  f"<input type='text' name='profiel' value='{e(v['set_naam'])}' maxlength='40'>"
                  f"<div class='balk'><button type='submit'>Gebruiken en bewaren</button></div></form></section>")
    return ("<div class='melding ok'>Gevonden. Kies de set die je wilt gebruiken; hij wordt ook bewaard als profiel.</div>"
            + "".join(f"<div class='melding let'>{e(m)}</div>" for m in meld) + rijen)


def kies_voorstel(f):
    """Knop 'Gebruiken en bewaren' na Zoek mijn set. Geeft (fouten, waarschuwingen)."""
    r = dict(STANDAARD)
    r.update(instellingen())
    for k in VOORSTEL_VELDEN:
        r[k] = (f.get(k) or "").strip()
    try:
        r["cat_model"], r["cat_baud"] = int(r["cat_model"] or 0), int(r["cat_baud"] or 0)
    except ValueError:
        return ["Ongeldige keuze; zoek opnieuw."], []
    if r["ptt_methode"] not in dict(METHODES):
        return ["Ongeldige keuze; zoek opnieuw."], []
    if r["modem"] not in ("auto", "1200", "300", "9600"):
        r["modem"] = "auto"
    poorten = usb.seriele_poorten()
    if r["ptt_methode"] == "CAT" and r["cat_poort"] not in poorten or \
            r["ptt_methode"] in ("RTS", "DTR") and r["ptt_poort"] not in poorten:
        return ["Deze poort is niet (meer) gevonden; zoek opnieuw."], []
    if r["geluidskaart"] and r["geluidskaart"] not in [k for _, k, _ in usb.geluidskaarten()]:
        return ["Deze geluidskaart is niet (meer) gevonden; zoek opnieuw."], []
    if r["ptt_methode"] != "CAT":
        r.update(cat_model=0, cat_poort="", cat_baud=0)
    fout = bewaar_profiel(f.get("profiel") or r["set_naam"], r)
    if fout:
        return [fout], []
    r["set_naam"] = re.sub(r"\s+", " ", str(f.get("profiel") or r["set_naam"])).strip()[:40]
    return pas_toe(r), []


# ---------------------------------------------------------------------------
# Handmatig opslaan en Station
# ---------------------------------------------------------------------------

def verwerk_handmatig(f):
    """Formulier 'Handmatig instellen'. Geeft (fouten, r)."""
    r = instellingen()
    fouten = []
    r["geluidskaart"] = (f.get("geluidskaart") or "").strip()
    r["ptt_methode"] = f.get("ptt_methode") if f.get("ptt_methode") in dict(METHODES) else "VOX"
    r["ptt_poort"] = (f.get("ptt_poort") or "").strip() if r["ptt_methode"] in ("RTS", "DTR") else ""
    r["modem"] = f.get("modem") if f.get("modem") in ("auto", "1200", "300", "9600") else "auto"
    try:
        r["txdelay_ms"] = max(50, min(1000, int(f.get("txdelay_ms") or 300)))
    except ValueError:
        fouten.append("TXDELAY: vul een getal in milliseconden in (bijv. 300).")
    if not r["geluidskaart"]:
        fouten.append("Kies de geluidskaart van de set.")
    if r["ptt_methode"] in ("RTS", "DTR") and not r["ptt_poort"]:
        fouten.append("Kies de PTT-poort, of kies VOX.")
    if r["ptt_methode"] == "CAT":
        try:
            r["cat_model"] = int(f.get("cat_model") or 0)
            r["cat_baud"] = int(f.get("cat_baud") or 0)
            v = (f.get("cat_watt") or "").strip().replace(",", ".").lower().replace("w", "").strip()
            r["cat_watt"] = float(v) if v else None
        except ValueError:
            fouten.append("CAT: kies een set, en vul het vermogen in als getal (watt).")
        r["cat_poort"] = (f.get("cat_poort") or "").strip()
        if not r.get("cat_model") or not r["cat_poort"]:
            fouten.append("CAT: kies je set en de CAT-poort (of gebruik Zoek mijn set).")
        if r.get("cat_watt") is not None and not 0.1 <= r["cat_watt"] <= 200:
            fouten.append("CAT: vul het zendvermogen in watt in (bijv. 25), of laat het leeg.")
        if not r.get("cat_baud"):
            r["cat_baud"] = next((b[0] for m, _, _, b in rig.MODELLEN if m == r.get("cat_model")), 19200)
        hf = int(r.get("cat_model") or 0) in rig.ALLEEN_HF or rig.is_hf(rig.doelfrequentie())
        r["cat_mode"] = "PKTUSB" if hf else "PKTFM"
    return fouten, r


def verwerk_station(f):
    """Roepnaam en frequentie. Geeft (fouten, station)."""
    s = station()
    fouten = []
    rn = schoon_call(f.get("roepnaam"))
    if not ROEPNAAM_RE.match(rn) or rn.startswith("N0CALL"):
        fouten.append("Roepnaam: gebruik je eigen roepnaam, eventueel met SSID (bijv. PD3PAM-7).")
    try:
        hz = int(f.get("frequentie") or 0)
    except ValueError:
        hz = -1
    if hz and hz not in rig.frequentie_keuzes():
        fouten.append("Kies een frequentie uit de lijst.")
    # Uitgeschakelde keuzelijst (eigen frequentie met een mode) wordt niet meegestuurd: vorige keuze bewaren
    mode = (f.get("mode") if "mode" in f else s.get("mode") or "").strip().upper()
    if mode not in dict(rig.MODES):
        fouten.append("Kies een mode uit de lijst.")
    pad = [x for x in re.split(r"[ ,]+", (f.get("pad") or "").strip().upper()) if x]
    if len(pad) > 2 or not all(ROEPNAAM_RE.match(x) for x in pad):
        fouten.append("Digipeaterpad: leeg laten, of bijv. WIDE1-1 (hoogstens twee, gescheiden door een komma).")
    if fouten:
        return fouten, s
    s.update(roepnaam=rn, frequentie=hz, mode=mode, pad=",".join(pad))
    schrijf(STATION_FILE, s)
    return [], s


# ---------------------------------------------------------------------------
# HTML van het tabblad Radio
# ---------------------------------------------------------------------------

def _opties(lijst, gekozen, leeg=None):
    uit = f'<option value="">{e(leeg)}</option>' if leeg else ""
    for waarde, tekst in lijst:
        uit += f'<option value="{e(str(waarde))}" {"selected" if str(waarde) == str(gekozen) else ""}>{e(tekst)}</option>'
    if gekozen and str(gekozen) not in [str(w) for w, _ in lijst]:
        uit += f'<option value="{e(str(gekozen))}" selected>{e(str(gekozen))} (niet gevonden!)</option>'
    return uit


MAX_EIGEN = 20


def verwerk_eigen(f):
    """Mijn frequenties: toevoegen of weghalen. Geeft (fouten, melding)."""
    s = station()
    lijst = rig.eigen_frequenties()
    if f.get("actie") == "weg":
        try:
            hz = int(f.get("hz") or 0)
        except ValueError:
            hz = 0
        s["eigen"] = [x for x in lijst if x["hz"] != hz]
        schrijf(STATION_FILE, s)
        return [], "Frequentie weggehaald."
    hz = rig.lees_mhz(f.get("mhz"))
    if not hz:
        return ["Frequentie: vul MHz in, bijv. 144,775 of 7,0449."], None
    if not rig.in_band(hz):
        return [f"{rig.mhz(hz)} ligt niet in een amateurband (160 m t/m 70 cm)."], None
    mode = (f.get("mode") or "").upper()
    baud = f.get("baud") or "auto"
    if mode not in dict(rig.MODES) or baud not in dict(rig.SNELHEDEN):
        return ["Kies een mode en snelheid uit de lijst."], None
    naam = re.sub(r"[^\w \-./]", "", (f.get("naam") or "").strip())[:30]
    lijst = [x for x in lijst if x["hz"] != hz]
    if len(lijst) >= MAX_EIGEN:
        return [f"Hoogstens {MAX_EIGEN} eigen frequenties; haal er eerst een weg."], None
    lijst.append({"hz": hz, "mode": mode, "baud": baud, "naam": naam})
    s["eigen"] = sorted(lijst, key=lambda x: x["hz"])
    schrijf(STATION_FILE, s)
    return [], f"{rig.mhz(hz)} toegevoegd. Kies hem bij Station en sla op."


def html_eigen(verborgen):
    lijst = rig.eigen_frequenties()
    rijen = "".join(
        f"<tr><td style='white-space:nowrap'>{e(rig.mhz(x['hz']).replace(' MHz', ''))}</td>"
        f"<td style='white-space:nowrap'>{e(rig.MODE_NAAM.get(x['mode']) or 'auto (' + rig.MODE_NAAM['PKTUSB' if rig.is_hf(x['hz']) else 'PKTFM'] + ')')}</td>"
        f"<td>{e(x['baud'])}</td><td>{e(x['naam'])}</td>"
        f"<td style='text-align:right'><form method='post' action='/frequentie' style='margin:0'>{verborgen}"
        f"<input type='hidden' name='actie' value='weg'><input type='hidden' name='hz' value='{x['hz']}'>"
        f"<button class='licht' type='submit'>Weg</button></form></td></tr>" for x in lijst)
    tabel = (f"<table><tr><th>MHz</th><th>Mode</th><th>Baud</th><th>Naam</th><th></th></tr>{rijen}</table>"
             if lijst else "")
    return f"""<section id="frequenties"><h2>Mijn frequenties</h2><p class="uitleg">Frequenties van stations, bakens en BBS'en bij jou
in de buurt, elk met de mode en snelheid die daar gebruikt worden. Ze komen in de lijst bij Station.</p>{tabel}
<details{'' if lijst else ' open'}><summary>Frequentie toevoegen</summary>
<form method="post" action="/frequentie">{verborgen}<input type="hidden" name="actie" value="toe">
<div class="rij"><div><label>Frequentie <small>MHz, bijv. 144,775</small></label>
<input type="text" name="mhz" inputmode="decimal" placeholder="144,775" required></div>
<div><label>Naam <small>optioneel</small></label><input type="text" name="naam" maxlength="30" placeholder="bijv. PD4R BBS"></div></div>
<div class="rij"><div><label>Mode</label><select name="mode">{_opties(rig.MODES, '')}</select></div>
<div><label>Snelheid</label><select name="baud">{_opties(rig.SNELHEDEN, 'auto')}</select></div></div>
<div class="balk"><button type="submit">Toevoegen</button></div></form></details></section>"""


def html_station(verborgen, s=None):
    s = s or station()
    rn = "" if str(s.get("roepnaam", "")).startswith("N0CALL") else s.get("roepnaam", "")
    return f"""<section id="station"><h2>Station</h2><p class="uitleg">Je roepnaam (met SSID, bijv. PD3PAM-7) en de frequentie.
Met CAT zet de Pi de set zelf op deze frequentie; zonder CAT zet je de set (het kanaal) zelf goed.</p>
<form method="post" action="/station">{verborgen}
<div class="rij"><div><label>Roepnaam</label><input type="text" name="roepnaam" value="{e(rn)}" placeholder="PD3PAM-7"
autocapitalize="characters" required></div>
<div><label>Frequentie <small>2 m, of uit Mijn frequenties</small></label>{rig.html_frequentie_keuze(s.get('frequentie'))}</div></div>
<label>Mode <small>alleen met CAT; bij Mijn frequenties geldt hun eigen mode</small></label>
<select name="mode" id="st_mode">{_opties(rig.MODES, s.get('mode') or '')}</select>
<p class="uitleg" id="st_mode_uitleg" style="margin:4px 0 0"></p>
<script>
(function () {{                     // eigen frequentie met een mode: die mode geldt, de keuzelijst doet dan niet mee
  var f = document.querySelector('select[name=frequentie]'), m = document.getElementById('st_mode'),
      u = document.getElementById('st_mode_uitleg');
  function kijk() {{
    var o = f.options[f.selectedIndex], v = o && o.getAttribute('data-mode');
    m.disabled = !!v;
    u.textContent = v ? 'Mode komt van Mijn frequenties: ' + v + '.' : '';
  }}
  f.addEventListener('change', kijk); kijk();
}})();
</script>
<label>Digipeaterpad <small>leeg = alleen rechtstreeks; bijv. WIDE1-1 om via een digipeater verder te komen</small></label>
<input type="text" name="pad" value="{e(s.get('pad') or '')}" placeholder="leeg" autocapitalize="characters">
<div class="balk"><button type="submit">Opslaan</button></div></form></section>"""


def html_set(verborgen, r, live=False):
    """Live gegevens van de set (CAT) of een duidelijke opdracht zonder CAT.
    De CAT-uitlezing kost op een Pi Zero tijd: zonder live=True komt er een plekhouder die de pagina zelf vult."""
    doel = rig.doelfrequentie()
    naam = r.get("set_naam") or "Set"
    if not rig.cat_actief(r):
        wat = (f"Zet je set op <b>{rig.mhz(doel)}</b>, FM (datamode als je set dat heeft)." if doel else
               "Zet je set zelf op de packetfrequentie, in FM (of USB-D op HF).")
        return (f"<section id='set'><h2>{e(naam)}</h2><div class='melding let' style='font-size:18px'>{wat}</div>"
                f"<p class='uitleg'>Deze set heeft geen CAT-besturing via de Pi; PTT: "
                f"{e(dict(METHODES).get(r.get('ptt_methode'), '-'))}. Modem {modem(r)} baud.</p></section>")
    live = html_set_live(r) if live else LADEN.format(deel="set", tekst="De set wordt uitgelezen…", hoog=190)
    log = "".join(f"<tr><td class='mono'>{e(t)}</td><td>{e(x)}</td></tr>" for t, x in rig.logregels())
    return f"""<section id="set"><h2>{e(naam)} (CAT)</h2><p class="uitleg">{e(rig.MODEL_NAAM.get(int(r.get('cat_model') or 0), ''))}
· ingesteld: <b>{rig.mhz(doel)}</b> · modem {modem(r)} baud. Draait iemand aan de set, dan zet de Pi hem terug.</p>{live}
<form method="post" action="/set_nu" class="balk">{verborgen}<button type="submit">Set nu instellen</button></form>
{('<details style="margin-top:10px"><summary>Laatste acties</summary><table>' + log + '</table></details>') if log else ''}</section>"""


def html_set_live(r=None):
    """Frequentie, mode, S-meter enz. via CAT (een stuk of zes vragen aan rigctld)."""
    r = r or instellingen()
    doel = rig.doelfrequentie()
    st = rig.status()
    if "fout" in st:
        live = f"<div class='melding fout'>Geen verbinding met de set via CAT: {e(st['fout'])}. Staat de set aan en klopt de CAT-poort?</div>"
    else:
        freq_goed = not doel or abs(st["frequentie"] - doel) <= 100
        mode_goed = rig.mode_goed(r, st.get("mode"))
        live = (f"<table><tr><td>Frequentie</td><td><b>{rig.mhz(st['frequentie'])}</b> "
                f"{'✓' if freq_goed else '<span style=color:var(--rood)>≠ ingesteld ' + rig.mhz(doel) + '</span>'}</td></tr>"
                f"<tr><td>Mode</td><td>{e(st.get('mode') or '?')} "
                f"{'✓' if mode_goed else '<span style=color:var(--rood)>verwacht: ' + rig.MODE_NAAM.get(rig.doelmode(r), '?') + '</span>'}</td></tr>"
                f"<tr><td>S-meter</td><td>{rig.s_meter(st.get('s'))}</td></tr>"
                f"<tr><td>Vermogen</td><td>{rig.watt_tekst(st)}</td></tr>"
                f"<tr><td>Zenden</td><td>{'ja' if st.get('ptt') else 'nee'}</td></tr></table>")
    return live


def html_zoek(verborgen):
    return f"""<form method="post" action="/set_zoek">{verborgen}<section id="zoek"><h2>Zoek mijn set</h2>
<p class="uitleg">De Pi kijkt welke sets er via USB aan hangen: Icom en Yaesu (CAT), DigiRig en losse USB-geluidskaarten.
Bij CAT-sets probeert hij de bekende modellen en snelheden. Zet de set aan. Dit duurt tot anderhalve minuut;
Direwolf is zolang even uit.</p>
<div class="melding let">Zet vóór het zoeken <b>PTT via RTS/DTR in de set uit</b> (IC-9700/IC-7300: <i>USB SEND</i> = OFF),
en zorg voor een goede antenne of dummyload. Anders kan de set kort gaan zenden als de Pi een poort opent.</div>
<button type="submit">Zoek mijn set</button></section></form>"""


def html_profielen(verborgen, r):
    p = profielen()
    rijen = ""
    for naam, x in sorted(p.items()):
        actief = naam == r.get("set_naam")
        ptt = "CAT" if x.get("ptt_methode") == "CAT" else x.get("ptt_methode", "")
        rijen += (f"<tr><td><b>{e(naam)}</b>{' <small>(in gebruik)</small>' if actief else ''}"
                  f"<br><small class='mono'>{e(str(x.get('geluidskaart') or '-'))} · {e(ptt)}</small></td>"
                  f"<td style='text-align:right;white-space:nowrap'><form method='post' action='/profiel' style='margin:0;display:inline'>"
                  f"{verborgen}<input type='hidden' name='naam' value='{e(naam)}'>"
                  f"<button type='submit' name='actie' value='gebruik'{' class=licht' if actief else ''}>Gebruiken</button> "
                  f"<button type='submit' name='actie' value='weg' class='licht' "
                  f"onclick=\"return confirm('Profiel verwijderen?')\">Weg</button></form></td></tr>")
    lijst = (f"<table>{rijen}</table>" if rijen else
             "<p class='uitleg'>Nog geen profielen. Gebruik <b>Zoek mijn set</b>: elke gekozen set wordt een profiel.</p>")
    return f"""<section id="sets"><h2>Mijn sets</h2><p class="uitleg">Wissel van set met één tik. Sluit de set eerst aan.</p>{lijst}
<form method="post" action="/profiel" class="balk" style="align-items:end">{verborgen}<input type="hidden" name="actie" value="bewaar">
<div style="flex:1;min-width:200px"><label style="margin-top:0">Huidige instellingen bewaren als</label>
<input type="text" name="naam" value="{e(r.get('set_naam') or '')}" maxlength="40" placeholder="bijv. IC-9700 shack"></div>
<button type="submit" class="licht">Bewaren</button></form></section>"""


def html_handmatig(verborgen, r):
    kaarten = [(k, f"{k} - {t}") for _, k, t in usb.geluidskaarten()]
    poorten = [(p, usb.korte_naam(p)) for p in usb.seriele_poorten()]
    verm = "" if r.get("cat_watt") in (None, "") else f"{float(r['cat_watt']):g}"
    return f"""<details id="handmatig"><summary>Handmatig instellen</summary><form method="post" action="/radio">{verborgen}
<section style="margin-top:10px"><p class="uitleg">Meestal niet nodig: Zoek mijn set vult dit in. Na opslaan worden Direwolf
en rigctld opnieuw gestart.</p>
<label>Geluidskaart van de set</label><select name="geluidskaart">{_opties(kaarten, r.get('geluidskaart'), '- kies -')}</select>
<label>Besturing</label><select name="ptt_methode" id="ptt_methode" onchange="toonCat()">{_opties(METHODES, r.get('ptt_methode'))}</select>
<div id="cat_deel">
<label>Set</label><select name="cat_model">{_opties([(m, f"{merk} {naam}") for m, merk, naam, _ in rig.MODELLEN], r.get('cat_model') or '', '- kies je set -')}</select>
<div class="rij"><div><label>CAT-poort</label><select name="cat_poort">{_opties(poorten, r.get('cat_poort') or '', '- kies -')}</select></div>
<div><label>Snelheid</label><select name="cat_baud">{_opties([(b, f"{b} baud") for b in rig.CAT_SNELHEDEN], r.get('cat_baud') or '', 'standaard van het model')}</select></div></div>
<label>Zendvermogen <small>in watt; leeg = niet aanpassen. Blijf binnen je vergunning.</small></label>
<input type="text" name="cat_watt" value="{e(verm)}" inputmode="decimal" placeholder="leeg = zoals de set staat"></div>
<div id="rts_deel"><label>PTT-poort</label><select name="ptt_poort">{_opties(poorten, r.get('ptt_poort') or '', '- kies -')}</select>
<p class="uitleg" style="margin-top:8px">DigiRig: de CP2102N-poort met RTS. FT-818 met SCU-17: poort B met RTS.</p></div>
<div class="rij"><div><label>Modem</label><select name="modem">{_opties([("auto", "Automatisch (zoals bij de frequentie; HF 300, anders 1200)"), ("1200", "1200 baud (VHF/UHF)"), ("300", "300 baud (HF)"), ("9600", "9600 baud (alleen sets met een 9k6-aansluiting)")], r.get('modem') or 'auto')}</select></div>
<div><label>TXDELAY <small>ms; Baofeng: 300-400</small></label><input type="number" name="txdelay_ms" min="50" max="1000" step="10" value="{e(str(r.get('txdelay_ms') or 300))}"></div></div>
<div class="balk"><button type="submit">Opslaan en herstarten</button></div></section></form></details>
<script>function toonCat(){{var m=document.getElementById('ptt_methode').value;
document.getElementById('cat_deel').style.display=m==='CAT'?'':'none';
document.getElementById('rts_deel').style.display=(m==='RTS'||m==='DTR')?'':'none';}}toonCat();</script>"""


def html_luister(verborgen, uitslag=None):
    meting = ""
    if uitslag:
        soort, tekst, piek, dbfs = uitslag
        cijfers = f" (piek {piek:g}%, gemiddeld {dbfs:g} dBFS)" if piek is not None else ""
        meting = f"<div class='melding {soort}'>{e(tekst)}{e(cijfers)}</div>"
    return f"""<section id="luister"><h2>Luistertest</h2><p class="uitleg">Komt er geluid van de set binnen? Open de
ruisonderdrukking (squelch) van de set, zodat je ruis hoort, en tik op de knop. De Pi luistert 5 seconden.
Werkt ook bij sets zonder CAT.</p>{meting}
<form method="post" action="/luistertest">{verborgen}<button type="submit" class="licht">Luister 5 seconden</button></form></section>"""


def html_test(verborgen, r, uitslag=""):
    m = mixer(r.get("geluidskaart"))
    ptt = "Geen PTT-aansluiting gekozen: de set moet op VOX staan." if r.get("ptt_methode") == "VOX" else ""

    def balk(sleutel, titel, uitleg):
        if sleutel not in m:
            return f"<label>{titel}</label><p class='uitleg'>Deze geluidskaart heeft geen regelaar hiervoor; stel het in op de set.</p>"
        naam, huidig = m[sleutel]
        waarde = r.get(f"niveau_{sleutel}", huidig)
        return (f'<label>{titel} <small>{e(uitleg)} (regelaar {e(naam)})</small></label>'
                f'<div style="display:flex;gap:12px;align-items:center"><input type="range" name="niveau_{sleutel}" min="0" max="100" '
                f'value="{int(waarde)}" style="flex:1" oninput="this.nextElementSibling.textContent=this.value+\'%\'">'
                f'<b style="min-width:3em">{int(waarde)}%</b></div>')

    return f"""<section id="test"><h2>Geluidsniveau en testuitzending</h2>{uitslag}
<form method="post" action="/radiotest">{verborgen}
{balk("zend", "Zendniveau", "Pi naar de set: bepaalt de zwaai")}
{balk("ontvang", "Ontvangstniveau", "set naar de Pi")}
<p class="uitleg" style="margin-top:8px">De testknoppen slaan eerst de niveaus op. Daarna zendt de Pi een kort testbericht
met jouw roepnaam. Gaat de set op <b>zenden</b> (zendlampje)? Luister op een tweede ontvanger: schoon packet-geluid,
niet vervormd. <b>Lang</b> houdt de zender ongeveer 6 seconden aan (vermogen en SWR aflezen).</p>
{f'<div class="melding let">{e(ptt)}</div>' if ptt else ''}
<div class="balk"><button type="submit" name="duur" value="kort">Opslaan + testuitzending</button>
<button type="submit" name="duur" value="lang" class="licht">Lang (6 s)</button>
<button type="submit" name="duur" value="opslaan" class="licht">Alleen opslaan</button></div></form>
<h3 style="margin-top:16px">Gehoorde stations (laatste 24 uur)</h3>
{LADEN.format(deel="gehoord", tekst="Het log van Direwolf wordt doorzocht…", hoog=60)}</section>"""


def html_gehoord():
    """Tabel met de gehoorde stations en hun audioniveau (uit het log van Direwolf; dat kost op een Pi Zero even)."""
    rijen = ""
    for x in gehoorde_stations():
        wanneer = time.strftime("%d-%m %H:%M", time.localtime(x["laatst"])) if x["laatst"] else "?"
        rijen += (f"<tr><td class='mono'><b>{e(x['call'])}</b></td><td class='mono'>{wanneer}</td>"
                  f"<td><b>{x['niveau']}</b></td><td>{e(advies_kort(x['niveau']))}</td><td>{x['aantal']}</td></tr>")
    return ("<table><tr><th>Station</th><th>Laatst</th><th>Niveau</th><th>Advies</th><th>Aantal</th></tr>" + rijen +
            "</table><p class='uitleg'>Niveau zoals Direwolf het meet; ideaal rond 50 (30-70).</p>") if rijen else \
        "<p class='uitleg'>De laatste 24 uur nog niemand gehoord.</p>"


def verwerk_test(roepnaam, f):
    """Formulier 'Geluidsniveau en testuitzending'. Geeft html met de uitslag."""
    r = instellingen()
    for sleutel in ("zend", "ontvang"):
        if f.get(f"niveau_{sleutel}") not in (None, ""):
            try:
                r[f"niveau_{sleutel}"] = max(0, min(100, int(f[f"niveau_{sleutel}"])))
            except ValueError:
                pass
    schrijf(RADIO_FILE, r)
    fouten = zet_niveaus(r)
    uit = "".join(f'<div class="melding fout">{e(x)}</div>' for x in fouten)
    if f.get("duur") in ("kort", "lang"):
        gelukt, regels = testuitzending(roepnaam, lang=f.get("duur") == "lang")
        if not gelukt:
            uit += "".join(f'<div class="melding fout">{e(x)}</div>' for x in regels)
        else:
            uit += ('<div class="melding ok">Testbericht naar Direwolf gestuurd. Ging de set op zenden? Zo niet: '
                    'controleer de besturing (PTT) bij Handmatig instellen.</div>')
            if regels:
                uit += '<pre class="mono">' + e("\n".join(regels)) + "</pre>"
    elif not fouten:
        uit += '<div class="melding ok">Niveaus opgeslagen en ingesteld.</div>'
    return uit


NA_EIGEN = []          # extra secties na Mijn frequenties (het APRS-baken), gezet door de webserver


# Plekhouder voor een traag deel: de pagina verschijnt meteen en haalt dit deel daarna op via /deel/<naam>
LADEN = "<div class='laden' data-deel='{deel}' style='min-height:{hoog}px'><p class='uitleg'>{tekst}</p></div>"


def html_radio(verborgen, bovenaan="", luister=None, test=""):
    r = instellingen()
    return (bovenaan + html_station(verborgen) + html_eigen(verborgen) + "".join(f(verborgen) for f in NA_EIGEN) +
            html_set(verborgen, r) + html_zoek(verborgen) + html_profielen(verborgen, r) +
            html_luister(verborgen, luister) + html_test(verborgen, r, test) + html_handmatig(verborgen, r))


def html_set_kort(r=None):
    """Eén regel voor het tabblad Status."""
    r = r or instellingen()
    doel = rig.doelfrequentie()
    naam = e(r.get("set_naam") or "Set")
    if not rig.cat_actief(r):
        return f"<tr><td>{naam}</td><td>{'Zet de set op <b>' + rig.mhz(doel) + '</b>' if doel else 'frequentie zelf ingesteld'} (geen CAT)</td></tr>"
    st = rig.status()
    if "fout" in st:
        return f"<tr><td>{naam} (CAT)</td><td style='color:var(--rood)'>geen verbinding - tabblad Radio</td></tr>"
    goed = not doel or abs(st["frequentie"] - doel) <= 100
    return (f"<tr><td>{naam} (CAT)</td><td><b>{rig.mhz(st['frequentie'])}</b> {e(st.get('mode') or '')} "
            f"{'✓' if goed else '<span style=color:var(--rood)>wordt teruggezet naar ' + rig.mhz(doel) + '</span>'}</td></tr>")


def hotspot_status():
    h = lees(HOTSPOT_FILE, {}) or {}
    aan = dienst_status("ax25chat-ap") == "active"
    st = _uit(["iw", "dev", "wlan0", "station", "dump"])
    return {"aan": aan, "ssid": h.get("ssid", ""), "wachtwoord": h.get("wachtwoord", ""), "clients": st.count("Station ")}


if __name__ == "__main__":
    if "--niveau" in sys.argv:          # door ax25chat-direwolf.service bij het starten
        for x in zet_niveaus():
            print(x, file=sys.stderr)
