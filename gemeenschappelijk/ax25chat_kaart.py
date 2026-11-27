#!/usr/bin/env python3
"""
ax25chat_kaart.py - offline kaart voor het tabblad Kaart (gehoorde stations) en de Android-app.

Downloadt eenmalig (met internet) de kaarttegels van de BRT-Achtergrondkaart van PDOK
(Kadaster, open data, CC BY 4.0) rond je eigen plek, zodat de kaart daarna zonder internet werkt.
De webserver serveert ze op http://10.42.0.1/tegels/{z}/{x}/{y}.png, voor de webpagina en de app.

Overgenomen uit Noodnet (noodnet_kaart.py). Anders dan in Noodnet: packet hoor je veel verder dan een
gemeente, dus een groot gebied (standaard 50 km) met minder detail, en meer detail rond het midden.

    python3 ax25chat_kaart.py --plaats Deventer --straal 50 --zoom 14
    python3 ax25chat_kaart.py --midden 52.255,6.163 --straal 50
    python3 ax25chat_kaart.py --status

Via ssh is er de opdracht  ax25chat-kaart  (dezelfde opties, zonder plaats: de vaste positie van het baken).
Heeft de Pi geen internet (Pi Zero op zijn eigen hotspot), dan gaat hij zelf even naar de bekende thuis-wifi,
downloadt de kaart en zet daarna de hotspot weer aan, net als bij het bijwerken. Dat gebeurt op de achtergrond,
want de ssh-verbinding via de hotspot valt dan weg. Een afgebroken download gaat de volgende keer verder.
"""

import argparse
import functools
import json
import math
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import ax25chat_systeem as systeem

MAP = systeem.MAP
KAART_DIR = os.path.join(MAP, "kaart")
TEGELS = os.path.join(KAART_DIR, "tegels")
NIEUW = os.path.join(KAART_DIR, "tegels.nieuw")
INFO_FILE = os.path.join(KAART_DIR, "kaart.json")
VOORTGANG_FILE = os.path.join(KAART_DIR, "voortgang.json")
BRON_FILE = os.path.join(MAP, "kaartbron.txt")

# Waar de ondergrond van de kaart vandaan komt (keuze op Radio, Kaart)
KAARTBRONNEN = {"auto": "Automatisch (offline en online)", "offline": "Alleen offline", "online": "Alleen online"}

TEGEL_URL = "https://service.pdok.nl/brt/achtergrondkaart/wmts/v2_0/standaard/EPSG:3857/{z}/{x}/{y}.png"
ZOEK_URL = ("https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?rows=1&fl=weergavenaam,centroide_ll,type"
            "&fq=type:(gemeente%20OR%20woonplaats)&q=")
AGENT = "AX25Chat/1.0 (+https://github.com/ieddev/AX25Chat)"
BRON = "Kaart: Kadaster / PDOK, BRT-Achtergrondkaart (CC BY 4.0)"

# Grof overzicht van de regio rond het gebied (voor het uitzoomen): 3x de straal, min. 150 km
REGIO_FACTOR = 3
REGIO_MIN_KM = 150
REGIO_ZOOM = (7, 9)
MIN_ZOOM_GEBIED = 10
STRALEN = (25, 50, 75, 100)            # km
STANDAARD_STRAAL, STANDAARD_ZOOM = 50, 14
ZOOMS = {12: "plaatsen en hoofdwegen", 13: "wegen", 14: "wegen en straatnamen (aanbevolen)"}
# Rond het midden (je eigen plek) altijd meer detail: straten, voor als je in de buurt rijdt
DETAIL_KM, DETAIL_ZOOM = 10, 15
GEM_KB = 14                            # gemiddelde grootte van een tegel, om te schatten
PARALLEL = 4
MAX_TEGELS = 40000                     # netjes blijven tegenover PDOK


# ---------------------------------------------------------------------------
# Rekenen met tegels (Web Mercator / slippy map)
# ---------------------------------------------------------------------------

def tegel_xy(lat, lon, z):
    lat = max(min(lat, 85.0511), -85.0511)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def gebied(lat, lon, straal_km):
    """(zuid, west, noord, oost) van een vierkant rond (lat, lon)."""
    dlat = straal_km / 111.32
    dlon = straal_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def tegels_in(bbox, zmin, zmax):
    z_, w, n_, o = bbox
    for z in range(zmin, zmax + 1):
        x1, y1 = tegel_xy(n_, w, z)
        x2, y2 = tegel_xy(z_, o, z)
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                yield z, x, y


def alle_tegels(lat, lon, straal_km, max_zoom):
    gezien = set()
    regio = max(straal_km * REGIO_FACTOR, REGIO_MIN_KM)
    for t in tegels_in(gebied(lat, lon, regio), *REGIO_ZOOM):
        gezien.add(t)
    for t in tegels_in(gebied(lat, lon, straal_km), MIN_ZOOM_GEBIED, max_zoom):
        gezien.add(t)
    for t in tegels_in(gebied(lat, lon, min(DETAIL_KM, straal_km)), max_zoom + 1, DETAIL_ZOOM):
        gezien.add(t)
    return sorted(gezien)


@functools.lru_cache(maxsize=16)          # het tabblad Radio vraagt steeds dezelfde schatting
def schatting(lat, lon, straal_km, max_zoom):
    n = len(alle_tegels(lat, lon, straal_km, max_zoom))
    return n, round(n * GEM_KB / 1024)


# ---------------------------------------------------------------------------
# Plaats zoeken (PDOK Locatieserver)
# ---------------------------------------------------------------------------

def zoek_plaats(naam, timeout=15):
    """Geeft (weergavenaam, lat, lon) of gooit een ValueError met uitleg."""
    url = ZOEK_URL + urllib.parse.quote(naam.strip())
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    docs = (data.get("response") or {}).get("docs") or []
    if not docs:
        raise ValueError(f"Plaats '{naam}' niet gevonden. Probeer de naam van de gemeente of woonplaats.")
    d = docs[0]
    punt = d.get("centroide_ll", "")            # "POINT(6.16 52.25)"
    try:
        lon, lat = (float(v) for v in punt[punt.index("(") + 1:punt.index(")")].split())
    except (ValueError, IndexError):
        raise ValueError(f"Geen coördinaten gevonden voor '{naam}'.")
    return d.get("weergavenaam") or naam, lat, lon


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def _lees(pad, standaard=None):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standaard


def _schrijf(pad, data):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tmp = pad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, pad)


def info():
    """Gegevens van de huidige offline kaart, of None."""
    return _lees(INFO_FILE)


def voortgang():
    """Voortgang van een download die bezig is (of net klaar/mislukt), of None."""
    v = _lees(VOORTGANG_FILE)
    if v and v.get("bezig") and time.time() - v.get("bijgewerkt", 0) > 120:
        v["bezig"] = False
        v["fout"] = v.get("fout") or "De download is onderbroken (AX25Chat herstart?). Start hem opnieuw."
    return v


# ---------------------------------------------------------------------------
# Downloaden
# ---------------------------------------------------------------------------

def _haal(t, doel, oud):
    z, x, y = t
    pad = os.path.join(doel, str(z), str(x), f"{y}.png")
    # Tegel die we al hebben (van de vorige kaart) niet opnieuw downloaden
    bestaand = os.path.join(oud, str(z), str(x), f"{y}.png")
    if os.path.exists(pad) and os.path.getsize(pad) > 0:
        return True                            # al binnen bij een eerdere, afgebroken poging
    if os.path.exists(bestaand) and os.path.getsize(bestaand) > 0:
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        shutil.copyfile(bestaand, pad)
        return True
    url = TEGEL_URL.format(z=z, x=x, y=y)
    for poging in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if not data:
                raise OSError("lege tegel")
            os.makedirs(os.path.dirname(pad), exist_ok=True)
            with open(pad + ".tmp", "wb") as f:
                f.write(data)
            os.replace(pad + ".tmp", pad)
            return True
        except urllib.error.HTTPError as fout:
            if fout.code in (400, 404):            # buiten het gebied van PDOK (buitenland): geen tegel, geen fout
                return True
            time.sleep(1 + 2 * poging)
        except Exception:
            time.sleep(1 + 2 * poging)
    return False


def download(plaats, lat, lon, straal_km, max_zoom):
    tegels = alle_tegels(lat, lon, straal_km, max_zoom)
    totaal = len(tegels)
    staat = {"bezig": True, "plaats": plaats, "klaar": 0, "mislukt": 0, "totaal": totaal,
             "start": time.time(), "bijgewerkt": time.time(), "fout": ""}
    _schrijf(VOORTGANG_FILE, staat)
    os.makedirs(NIEUW, exist_ok=True)          # wat er al in staat (afgebroken download) wordt niet opnieuw gehaald
    scherm = sys.stdout.isatty()
    lock = threading.Lock()
    gestopt = threading.Event()

    def een(t):
        if gestopt.is_set():
            with lock:
                staat["mislukt"] += 1
            return False
        ok = _haal(t, NIEUW, TEGELS)
        if not ok and staat["klaar"] == 0 and staat["mislukt"] >= 8:
            gestopt.set()                              # niets lukt: geen internet, niet uren blijven proberen
        with lock:
            staat["klaar" if ok else "mislukt"] += 1
            if (staat["klaar"] + staat["mislukt"]) % 50 == 0:
                staat["bijgewerkt"] = time.time()
                _schrijf(VOORTGANG_FILE, staat)
                if scherm:
                    gedaan = staat["klaar"] + staat["mislukt"]
                    print(f"\r   {gedaan} van {totaal} tegels ({100 * gedaan // totaal}%)", end="", flush=True)
        return ok

    with ThreadPoolExecutor(PARALLEL) as pool:
        list(pool.map(een, tegels))

    staat["bezig"] = False
    staat["bijgewerkt"] = time.time()
    # Veel mislukt (geen internet?): de oude kaart houden
    if staat["klaar"] < totaal * 0.9:
        staat["fout"] = ("Geen verbinding met de kaartserver (PDOK). Is er internet (thuis-wifi of netwerkkabel)? "
                         "De vorige kaart blijft staan." if gestopt.is_set() else
                         f"{staat['mislukt']} van {totaal} tegels konden niet gedownload worden. "
                         "Is er internet? De vorige kaart blijft staan.")
        _schrijf(VOORTGANG_FILE, staat)
        return False                           # tegels.nieuw blijft staan: de volgende keer gaat hij verder
    oud = os.path.join(KAART_DIR, "tegels.oud")
    shutil.rmtree(oud, ignore_errors=True)
    if os.path.isdir(TEGELS):
        os.replace(TEGELS, oud)
    os.replace(NIEUW, TEGELS)
    shutil.rmtree(oud, ignore_errors=True)
    _schrijf(INFO_FILE, {"plaats": plaats, "lat": round(lat, 6), "lon": round(lon, 6), "straal_km": straal_km,
                         "max_zoom": max(max_zoom, DETAIL_ZOOM), "detail_zoom": max_zoom, "zoom_start": 10, "aantal": staat["klaar"],
                         "mislukt": staat["mislukt"], "datum": time.strftime("%Y-%m-%d %H:%M"),
                         "bron": BRON, "gebied": gebied(lat, lon, straal_km),
                         "detail_gebied": gebied(lat, lon, min(DETAIL_KM, straal_km))})
    _schrijf(VOORTGANG_FILE, staat)
    return True


# ---------------------------------------------------------------------------
# Voor de webserver (tabblad Radio: downloaden; tabblad Kaart en de app: tonen)
# ---------------------------------------------------------------------------

def _e(t):
    import html as _h
    return _h.escape(str(t), quote=True)


_MB = {}                 # pad -> (tijd van kaart.json, MB): alle tegels langslopen duurt op een Pi Zero lang


def map_mb(pad=TEGELS):
    try:
        sleutel = os.path.getmtime(INFO_FILE)
    except OSError:
        sleutel = None
    if sleutel and _MB.get(pad, (None,))[0] == sleutel:
        return _MB[pad][1]
    totaal = 0
    for wortel, _, bestanden in os.walk(pad):
        for b in bestanden:
            try:
                totaal += os.path.getsize(os.path.join(wortel, b))
            except OSError:
                pass
    mb = round(totaal / 1024 / 1024)
    if sleutel:
        _MB[pad] = (sleutel, mb)
    return mb


def tegel_pad(z, x, y):
    """Pad van een kaarttegel, of None als de waarden niet kloppen of de tegel er niet is."""
    try:
        z, x, y = int(z), int(x), int(str(y).removesuffix(".png"))
    except (TypeError, ValueError):
        return None
    if not (0 <= z <= 20 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return None
    pad = os.path.join(TEGELS, str(z), str(x), f"{y}.png")
    return pad if os.path.isfile(pad) else None


def kaartbron():
    """'auto', 'offline' of 'online'."""
    try:
        with open(BRON_FILE, encoding="utf-8") as f:
            v = f.read().strip()
    except OSError:
        v = ""
    return v if v in KAARTBRONNEN else "auto"


def zet_kaartbron(v):
    """Bewaar de keuze. Geeft een foutmelding of ''."""
    if v not in KAARTBRONNEN:
        return "Kies waar de kaart vandaan komt."
    try:
        os.makedirs(MAP, exist_ok=True)
        with open(BRON_FILE, "w", encoding="utf-8") as f:
            f.write(v + "\n")
    except OSError as fout:
        return f"Opslaan lukte niet: {fout}"
    return ""


def voor_kaart():
    """Wat de kaartpagina en de app nodig hebben: {'kaart': bool (offline kaart aanwezig), midden, zoom's, gebieden,
    bron, kaartbron (auto/offline/online), online_url}."""
    basis = {"kaart": False, "kaartbron": kaartbron(), "online_url": TEGEL_URL, "bron": BRON}
    k = info()
    if not k or not os.path.isdir(TEGELS):
        return basis
    return dict(basis, kaart=True, midden=[k.get("lat"), k.get("lon")], plaats=k.get("plaats", ""),
                max_zoom=k.get("detail_zoom", k.get("max_zoom", 14)), detail_zoom=k.get("max_zoom", DETAIL_ZOOM),
                gebied=k.get("gebied"), detail_gebied=k.get("detail_gebied"), bron=k.get("bron", BRON),
                datum=k.get("datum", ""))


def start_download(plaats, straal, zoom, positie=None):
    """Download op de achtergrond starten. plaats leeg en positie (lat, lon): rond die positie.
    Geeft een foutmelding, of '' als hij loopt."""
    import subprocess
    plaats = " ".join(str(plaats or "").split())[:60]
    try:
        straal, zoom = int(straal), int(zoom)
    except (TypeError, ValueError):
        straal = zoom = 0
    if straal not in STRALEN or zoom not in ZOOMS:
        return "Kies straal en detail."
    if not plaats and not positie:
        return "Vul een plaats in (of vul bij het APRS-baken je vaste positie in)."
    v = voortgang()
    if v and v.get("bezig"):
        return "Er loopt al een download."
    os.makedirs(KAART_DIR, exist_ok=True)
    _schrijf(VOORTGANG_FILE, {"bezig": True, "plaats": plaats or "mijn positie", "klaar": 0, "mislukt": 0, "totaal": 0,
                              "bijgewerkt": time.time(), "fout": ""})
    waar = ["--plaats", plaats] if plaats else ["--midden", f"{positie[0]:.5f},{positie[1]:.5f}"]
    if getattr(sys, "frozen", False):         # Windows-programma (één .exe): downloaden in een draad, niet als los proces
        threading.Thread(target=main, args=([*waar, "--straal", str(straal), "--zoom", str(zoom), "--niet-wisselen"],),
                         daemon=True).start()
        return ""
    with open(os.path.join(KAART_DIR, "download.log"), "w") as logf:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), *waar, "--straal", str(straal),
                          "--zoom", str(zoom)], stdout=logf, stderr=subprocess.STDOUT, start_new_session=True, cwd=MAP)
    return ""


def stand_json():
    """Voortgang voor de pagina (ververst zichzelf tijdens het downloaden)."""
    v = voortgang() or {}
    return {"bezig": bool(v.get("bezig")), "klaar": (v.get("klaar") or 0) + (v.get("mislukt") or 0),
            "totaal": v.get("totaal") or 0, "fout": v.get("fout") or "", "plaats": v.get("plaats", ""),
            "stap": v.get("stap", "")}


def html_beheer(verborgen, positie=None):
    """Sectie op het tabblad Radio: huidige offline kaart, voortgang en het formulier om (opnieuw) te downloaden."""
    k = info()
    v = voortgang()
    bezig = bool(v and v.get("bezig"))
    if k:
        huidig = (f"<p>Offline kaart van <b>{_e(k.get('plaats', ''))}</b>, straal {_e(k.get('straal_km', ''))} km, "
                  f"{k.get('aantal', 0)} tegels ({map_mb()} MB), gedownload {_e(k.get('datum', ''))}.</p>")
    else:
        huidig = ("<p><b>Nog geen offline kaart.</b> Gehoorde stations staan wel op het tabblad Kaart, "
                  + ("maar zonder ondergrond.</p>" if kaartbron() == "offline" else
                     "met de kaart van internet als die er is.</p>"))
    melding = ""
    if v and (bezig or v.get("fout") or time.time() - v.get("bijgewerkt", 0) < 600):
        if bezig:
            melding = ("<div class='melding let' id='kaart_stand'>" + _e(v.get("stap") or "Bezig met downloaden...") +
                       "</div>")
        elif v.get("fout"):
            melding = f"<div class='melding fout'>{_e(v['fout'])}</div>"
        else:
            melding = f"<div class='melding ok'>Kaart gedownload: {v.get('klaar', 0)} tegels.</div>"
    plaats = (k or {}).get("plaats", "")
    if plaats[:1].isdigit() or plaats.startswith("-"):
        plaats = ""                                  # was rond een positie
    plaats = plaats.split(",")[0].removeprefix("Gemeente ").strip()
    straal = (k or {}).get("straal_km", STANDAARD_STRAAL)
    zoom = (k or {}).get("detail_zoom", STANDAARD_ZOOM)
    o_straal = "".join(f'<option value="{s}" {"selected" if s == straal else ""}>{s} km</option>' for s in STRALEN)
    o_zoom = "".join(f'<option value="{z}" {"selected" if z == zoom else ""}>{_e(t)}</option>' for z, t in ZOOMS.items())
    n, mb = schatting(52.2, 5.5, STANDAARD_STRAAL, STANDAARD_ZOOM)
    pos = (f"Laat je leeg, dan neemt AX25Chat je vaste positie van het APRS-baken "
           f"({positie[0]:.4f}, {positie[1]:.4f})." if positie else
           "Laat je leeg, dan neemt AX25Chat de vaste positie van het APRS-baken (nu nog niet ingevuld).")
    knop = "<button type='submit' disabled>Bezig...</button>" if bezig else "<button type='submit'>Kaart downloaden</button>"
    ververs = """<script>(function(){var el=document.getElementById('kaart_stand');if(!el)return;
function kijk(){fetch('/api/kaart').then(function(r){return r.json()}).then(function(d){var s=d.download||{};
if(!s.bezig){location.reload();return}
el.textContent=(!s.totaal&&s.stap)?s.stap:'Bezig met downloaden voor '+s.plaats+': '+s.klaar+' van '+(s.totaal||'?')+' tegels'+
(s.totaal?' ('+Math.floor(100*s.klaar/s.totaal)+'%)':'')+'.';setTimeout(kijk,3000)}).catch(function(){setTimeout(kijk,5000)})}
kijk()})()</script>""" if bezig else ""
    uitleg_na = ("""<p class="uitleg">De vorige kaart blijft werken tot de nieuwe helemaal binnen is. Heeft de Pi geen internet (een Pi
Zero op zijn eigen hotspot), dan gaat hij zelf even naar je bekende thuis-wifi en zet daarna de hotspot weer aan, net
als bij het bijwerken. Deze pagina is dan een paar minuten weg; verbind daarna opnieuw met de hotspot. Via ssh kan
het ook: <span class="mono">ax25chat-kaart</span> (zie de procedure).</p>""" if systeem.kan("hotspot") else
                 '<p class="uitleg">De vorige kaart blijft werken tot de nieuwe helemaal binnen is. De kaart wordt '
                 'opgeslagen in de map van AX25Chat en werkt daarna ook zonder internet.</p>')
    bron = kaartbron()
    o_bron = "".join(f'<option value="{w}" {"selected" if w == bron else ""}>{_e(t)}</option>'
                     for w, t in KAARTBRONNEN.items())
    keuze = f"""<form method="post" action="/kaartbron" class="rij" style="align-items:flex-end;margin:6px 0 14px">{verborgen}
<div style="flex:3 1 260px"><label>Kaart op het tabblad Kaart</label><select name="kaartbron">{o_bron}</select></div>
<div style="flex:0 0 auto"><button type="submit" class="licht">Opslaan</button></div></form>
<p class="uitleg" style="margin-top:-6px"><b>Automatisch:</b> de offline kaart waar je die hebt gedownload,
daaromheen en bij verder inzoomen de kaart van internet. <b>Alleen offline:</b> nooit internet.
<b>Alleen online:</b> altijd van internet, ook zonder gedownloade kaart. Online haalt de browser de kaart zelf van PDOK; dat werkt alleen als het
apparaat waarop je kijkt internet heeft. Op de hotspot van de Pi is dat meestal niet zo: daar helpt alleen de offline
kaart. De app gebruikt altijd de offline kaart.</p>"""
    return f"""<section id="kaarten"><h2>Kaart</h2>{keuze}<h3 style="margin:10px 0 4px">Offline kaart</h3>
<p class="uitleg">Voor het tabblad <b>Kaart</b> en de app: de stations die je hoort, op een kaart die zonder internet
werkt. Download hem <b>eenmalig met internet</b> (thuis-wifi of netwerkkabel). Kaart: BRT-Achtergrondkaart van het
Kadaster via PDOK (open data, CC BY 4.0). Die dekt alleen Nederland: stations over de grens staan er wel op, maar
zonder ondergrond. Met de standaardkeuze (50 km, aanbevolen detail) zijn het ongeveer {f'{round(n, -3):,}'.replace(',', '.')} tegels en {round(mb, -1)} MB, een
paar minuten downloaden. Rond het midden komt meer detail (straten, {DETAIL_KM} km), daaromheen een grof overzicht.</p>
{melding}{huidig}
<form method="post" action="/kaart">{verborgen}
<label>Midden van de kaart <small>gemeente of woonplaats</small></label>
<input type="text" name="plaats" value="{_e(plaats)}" maxlength="60" placeholder="bijv. Deventer">
<p class="uitleg" style="margin:4px 0 0">{_e(pos)}</p>
<div class="rij"><div><label>Straal rondom het midden</label><select name="straal">{o_straal}</select></div>
<div><label>Detail</label><select name="zoom">{o_zoom}</select></div></div>
<div class="balk" style="margin-top:10px">{knop}</div></form>
{uitleg_na}{ververs}</section>"""


# ---------------------------------------------------------------------------
# Zonder internet: even naar de thuis-wifi (Pi Zero: wifi is óf hotspot óf thuis-wifi)
# ---------------------------------------------------------------------------

def internet(timeout=8):
    try:
        req = urllib.request.Request(TEGEL_URL.format(z=7, x=66, y=42), headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(1)
        return True
    except urllib.error.HTTPError:
        return True                             # PDOK antwoordt: er is internet
    except Exception:
        return False


def _wifi(actie):
    """Hotspot uit en thuis-wifi aan ('thuiswifi'), of terug ('hotspot'). Zelfde dienst als het bijwerken."""
    import subprocess
    r = subprocess.run(["sudo", "-n", "systemctl", "start", "--no-block", f"ax25chat-wifi@{actie}"],
                       capture_output=True, text=True, timeout=20)
    return r.returncode == 0


def thuiswifi():
    """(naam van de bekende thuis-wifi of None, staat de hotspot nu aan?)"""
    if not systeem.kan("hotspot"):
        return None, False                      # PC: gewoon het eigen internet gebruiken
    try:
        import ax25chat_bijwerken as bw
        return bw.thuiswifi_naam(), not bw.thuiswifi_actief()
    except Exception:
        return None, False


def vaste_positie():
    """Vaste positie van het APRS-baken (tabblad Radio), of None."""
    b = (_lees(os.path.join(MAP, "station.json"), {}) or {}).get("baken") or {}
    if b.get("lat") is None or b.get("lon") is None:
        return None
    return float(b["lat"]), float(b["lon"])


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="ax25chat-kaart",
        description="Offline kaart (PDOK) voor AX25Chat downloaden. Zonder plaats: rond de vaste positie van het baken.")
    ap.add_argument("plaats_los", nargs="?", metavar="PLAATS", help="gemeente of woonplaats, bijv. Deventer")
    ap.add_argument("--plaats", help=argparse.SUPPRESS)
    ap.add_argument("--midden", help="lat,lon in plaats van een plaats, bijv. 52.255,6.163")
    ap.add_argument("--straal", type=int, default=STANDAARD_STRAAL,
                    help=f"km rond het midden: {', '.join(map(str, STRALEN))} (standaard {STANDAARD_STRAAL})")
    ap.add_argument("--zoom", type=int, default=STANDAARD_ZOOM, choices=sorted(ZOOMS),
                    help=f"detail: 12 plaatsen en hoofdwegen, 13 wegen, 14 straatnamen (standaard {STANDAARD_ZOOM})")
    ap.add_argument("--schat", action="store_true", help="alleen het aantal tegels en de grootte tonen")
    ap.add_argument("--status", action="store_true", help="hoe staat de download ervoor (ook als hij op de achtergrond loopt)")
    ap.add_argument("--niet-wisselen", action="store_true",
                    help="zonder internet niet zelf naar de thuis-wifi gaan")
    ap.add_argument("--wissel", action="store_true", help=argparse.SUPPRESS)   # intern: draait al op de achtergrond
    a = ap.parse_args(argv)
    a.plaats = a.plaats or a.plaats_los
    if a.status:
        return toon_status()
    if not (1 <= a.straal <= max(STRALEN)):
        print(f"Straal moet tussen 1 en {max(STRALEN)} km zijn."); return 1
    if not a.plaats and not a.midden:
        pos = vaste_positie()
        if not pos:
            print("Geef een plaats (bijv.  ax25chat-kaart Deventer ) of vul bij het APRS-baken een vaste positie in."); return 1
        a.midden = f"{pos[0]:.5f},{pos[1]:.5f}"
    v = voortgang()
    if v and v.get("bezig") and sys.stdin and sys.stdin.isatty() and time.time() - v.get("bijgewerkt", 0) < 120:
        print("Er loopt al een download. Volg hem met:  ax25chat-kaart --status"); return 1

    if a.wissel:
        return met_thuiswifi(a)
    if not a.schat and not internet():
        naam, hotspot = thuiswifi()
        if a.niet_wisselen or not naam or not hotspot:
            fout = ("Geen internet. " + ("Er is geen thuis-wifi bekend op deze Pi (Raspberry Pi Imager of nmtui). " if not naam
                    else "") + "Sluit een netwerkkabel aan, of zet op het tabblad Status de thuis-wifi aan.")
            _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
            print(fout); return 1
        return start_met_thuiswifi(naam)
    return downloaden(a)


def downloaden(a):
    try:
        if a.midden:
            lat, lon = (float(v) for v in a.midden.split(","))
            plaats = a.plaats or f"{lat:.4f}, {lon:.4f}"
        else:
            plaats, lat, lon = zoek_plaats(a.plaats)
    except ValueError as ex:
        fout = str(ex)
    except OSError:
        fout = "Geen verbinding met PDOK. Is er internet? (netwerkkabel, of tijdelijk de thuis-wifi)"
    else:
        fout = ""
    if fout:
        _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
        print(fout); return 1
    n, mb = schatting(lat, lon, a.straal, a.zoom)
    print(f"{plaats} ({lat:.4f}, {lon:.4f}), {a.straal} km, zoom t/m {a.zoom}: {n} tegels, ongeveer {mb} MB")
    if a.schat:
        return 0
    if n > MAX_TEGELS:
        fout = f"Te groot: {n} tegels (max. {MAX_TEGELS}). Kies een kleinere straal of minder detail."
        _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
        print(fout); return 1
    ok = download(plaats, lat, lon, a.straal, a.zoom)
    v = voortgang() or {}
    if sys.stdout.isatty():
        print()
    print("Klaar: de kaart staat op het tabblad Kaart." if ok else v.get("fout", "Mislukt."),
          f"({v.get('klaar', 0)} gelukt, {v.get('mislukt', 0)} mislukt)")
    return 0 if ok else 1


def start_met_thuiswifi(naam):
    """Op de achtergrond verder: de ssh-verbinding via de hotspot valt zo weg."""
    import subprocess
    os.makedirs(KAART_DIR, exist_ok=True)
    _schrijf(VOORTGANG_FILE, {"bezig": True, "plaats": "", "klaar": 0, "mislukt": 0, "totaal": 0,
                              "bijgewerkt": time.time(), "fout": "",
                              "stap": f"Geen internet: de Pi gaat even naar de thuis-wifi '{naam}'."})
    with open(os.path.join(KAART_DIR, "download.log"), "w") as logf:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), *sys.argv[1:], "--wissel"], stdout=logf,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, cwd=MAP)
    print(f"""De Pi heeft geen internet. Hij gaat nu even naar je thuis-wifi '{naam}', downloadt de kaart en zet
daarna de hotspot weer aan (net als bij het bijwerken). Dat gaat op de achtergrond verder.

Ben je via de hotspot verbonden, dan valt deze ssh-verbinding zo weg. Na een paar minuten (bij 50 km
ongeveer 5 tot 10) is de hotspot terug. Verbind dan opnieuw en kijk met:  ax25chat-kaart --status
Lukt de thuis-wifi niet, dan komt de hotspot meteen terug; na 60 minuten in elk geval.""")
    return 0


def met_thuiswifi(a):
    """Draait op de achtergrond: thuis-wifi aan, wachten op internet, downloaden, hotspot weer aan."""
    print(time.strftime("%H:%M:%S"), "thuis-wifi aan", flush=True)
    time.sleep(3)                               # ssh-gebruiker kan de uitleg nog lezen
    if not _wifi("thuiswifi"):
        fout = "Thuis-wifi aanzetten lukte niet (sudo). Werk de Pi eerst bij: ax25chat-bijwerken."
        _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
        print(fout); return 1
    ok = False
    try:
        for _ in range(30):                     # tot 2,5 minuut wachten op internet
            time.sleep(5)
            v = voortgang() or {}
            v.update(bezig=True, bijgewerkt=time.time(), stap="Verbinden met de thuis-wifi…")
            _schrijf(VOORTGANG_FILE, v)
            if internet():
                ok = True
                break
        if not ok:
            fout = "Via de thuis-wifi was er geen internet. Klopt het wachtwoord, en is de thuis-wifi in de buurt?"
            _schrijf(VOORTGANG_FILE, {"bezig": False, "fout": fout, "bijgewerkt": time.time()})
            print(fout)
            return 1
        print(time.strftime("%H:%M:%S"), "internet, downloaden", flush=True)
        return downloaden(a)
    finally:
        print(time.strftime("%H:%M:%S"), "hotspot weer aan", flush=True)
        _wifi("hotspot")


def toon_status():
    k, v = info(), voortgang() or {}
    if k:
        print(f"Offline kaart: {k.get('plaats')}, straal {k.get('straal_km')} km, {k.get('aantal')} tegels "
              f"({map_mb()} MB), gedownload {k.get('datum')}.")
    else:
        print("Nog geen offline kaart.")
    if v.get("bezig"):
        totaal = v.get("totaal") or 0
        gedaan = (v.get("klaar") or 0) + (v.get("mislukt") or 0)
        print(f"Bezig: {gedaan} van {totaal or '?'} tegels" + (f" ({100 * gedaan // totaal}%)." if totaal else ".")
              + (" " + v["stap"] if v.get("stap") and not totaal else ""))
    elif v.get("fout"):
        print("Laatste poging mislukt:", v["fout"])
    log = os.path.join(KAART_DIR, "download.log")
    if os.path.exists(log):
        print("Log:", log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
