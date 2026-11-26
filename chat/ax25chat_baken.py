"""
ax25chat_baken.py - APRS-positiebaken op 144,800 MHz, vooral voor mobiel gebruik.

- Positie uit een GPS-ontvanger via USB (NMEA, bijv. een u-blox-stickje), of een vaste positie die je zelf invult.
  (De GPS van de telefoon kan niet: de browser geeft de locatie alleen aan https-pagina's, en de Pi is http.)
- Alleen als je positie verandert: tijdens het rijden met een vast interval (10-30 min), of met "vaker tijdens het
  rijden" (SmartBeaconing): hoe harder je rijdt, hoe vaker, en ook na een bocht. Stilstaand niets, of als je dat
  aanzet eens per uur, zodat je op de kaart zichtbaar blijft.
- Tijdens een BBS-, node- of chatverbinding (tabblad BBS) pauzeert het baken; na het verbreken gaat het verder.
- Alleen als de set op 144,800 staat (Station). Staat hij voor een BBS of chat op een andere frequentie, dan wacht het
  baken: anders zou het je positie midden in een gesprek of op de verkeerde frequentie uitzenden.

Alleen standaard-Python.
"""

import math
import os
import re
import select
import termios
import threading
import time

import ax25chat_ax25 as ax25
import ax25chat_radio as radio
import ax25chat_rig as rig
import ax25chat_usb as usb

INTERVALLEN = [10, 15, 20, 30]                  # minuten
SYMBOLEN = [(">", "Auto"), ("v", "Bus/camper"), ("j", "Jeep"), ("k", "Vrachtwagen"), ("<", "Motor"), ("b", "Fiets"),
            ("[", "Lopend"), ("-", "Huis"), (";", "Portabel (tent)"), ("s", "Boot")]
STANDAARD = {"aan": False, "bron": "gps", "gps_poort": "", "lat": None, "lon": None, "interval": 20, "slim": True,
             "symbool": ">", "commentaar": "AX25Chat", "pad": "WIDE1-1,WIDE2-1", "stilstaand": False}

# SmartBeaconing (waarden zoals in de meeste trackers)
TRAAG_KMH, SNEL_KMH = 5, 90                      # onder 5 km/h: stilstaan; vanaf 90 km/h: het snelst
SNEL_SEC = 180                                   # bij 90 km/h en harder: elke 3 minuten
BOCHT_MIN_GRADEN, BOCHT_HELLING, BOCHT_MIN_SEC = 28, 255, 30
MIN_SEC = 60                                     # nooit vaker dan eens per minuut
GPS_VERS = 30                                    # een GPS-positie ouder dan 30 s telt niet
VERPLAATST_M = 200                               # pas na 200 m telt het als een andere positie (GPS verspringt wat)
STIL_SEC = 3600                                  # stilstaand (als aangezet): eens per uur


def instellingen():
    b = dict(STANDAARD)
    b.update(radio.station().get("baken") or {})
    return b


# ---------------------------------------------------------------------------
# GPS (NMEA)
# ---------------------------------------------------------------------------

def nmea_ok(regel):
    """Klopt de checksum van deze NMEA-regel?"""
    m = re.fullmatch(r"\$([^*]+)\*([0-9A-Fa-f]{2})", regel.strip())
    if not m:
        return False
    som = 0
    for c in m.group(1):
        som ^= ord(c)
    return som == int(m.group(2), 16)


def _graden(waarde, halfrond):
    if not waarde:
        return None
    punt = waarde.index(".") if "." in waarde else len(waarde)
    g = int(waarde[:punt - 2]) + float(waarde[punt - 2:]) / 60
    return -g if halfrond in ("S", "W") else g


def lees_rmc(regel):
    """$GPRMC/$GNRMC -> {'lat', 'lon', 'kmh', 'koers'} of None (geen geldige positie)."""
    if not nmea_ok(regel):
        return None
    d = regel.strip()[1:].split("*")[0].split(",")
    if len(d) < 9 or not d[0].endswith("RMC") or d[2] != "A":
        return None
    try:
        lat, lon = _graden(d[3], d[4]), _graden(d[5], d[6])
        kmh = float(d[7] or 0) * 1.852
        koers = float(d[8]) if d[8] else None
    except (ValueError, IndexError):
        return None
    if lat is None or lon is None:
        return None
    return {"lat": lat, "lon": lon, "kmh": kmh, "koers": koers}


def _open_serieel(pad, baud=9600):
    fd = os.open(pad, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    snelheid = getattr(termios, f"B{baud}", termios.B9600)
    a[0] = termios.IGNPAR                              # iflag
    a[1] = 0                                           # oflag
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    a[3] = 0                                           # lflag: geen echo, niet regel voor regel
    a[4] = a[5] = snelheid
    termios.tcsetattr(fd, termios.TCSANOW, a)
    return fd


def is_gps(pad, seconden=3):
    """Komt er NMEA uit deze poort? (voor Zoek GPS)"""
    try:
        fd = _open_serieel(pad)
    except OSError:
        return False
    try:
        buf, eind = b"", time.time() + seconden
        while time.time() < eind:
            if select.select([fd], [], [], 0.5)[0]:
                buf += os.read(fd, 1024)
                if re.search(rb"\$G[PNLA](RMC|GGA)", buf):
                    return True
        return False
    except OSError:
        return False
    finally:
        os.close(fd)


def kandidaat_poorten():
    """Seriële poorten die geen CAT- of PTT-poort van de set zijn (die openen kan de set laten zenden)."""
    r = radio.instellingen()
    bezet = {os.path.realpath(p) for p in (r.get("cat_poort"), r.get("ptt_poort")) if p}
    return [p for p in usb.seriele_poorten() if os.path.realpath(p) not in bezet]


def zoek_gps():
    return next((p for p in kandidaat_poorten() if is_gps(p)), "")


class Gps:
    """Leest NMEA van de ingestelde poort en onthoudt de laatste geldige positie."""

    def __init__(self, lees_poort, log=print):
        self.lees_poort = lees_poort
        self.log = log
        self.fix = None                       # {'lat', 'lon', 'kmh', 'koers', 'tijd'}
        self.stand = "geen GPS ingesteld"
        threading.Thread(target=self._run, daemon=True).start()

    def positie(self):
        f = self.fix
        return f if f and time.time() - f["tijd"] < GPS_VERS else None

    def _run(self):
        while True:
            pad = self.lees_poort()
            if not pad:
                self.stand, self.fix = "geen GPS ingesteld", None
                time.sleep(3)
                continue
            try:
                fd = _open_serieel(pad)
            except OSError as e:
                self.stand = f"GPS niet gevonden ({os.path.basename(pad)}): {e.strerror or e}"
                time.sleep(5)
                continue
            self.stand = "GPS gevonden, wacht op een positie (buiten, vrij zicht op de lucht)"
            buf = b""
            try:
                while self.lees_poort() == pad:
                    if not select.select([fd], [], [], 2)[0]:
                        continue
                    data = os.read(fd, 1024)
                    if not data:
                        raise OSError("GPS losgehaald")
                    buf = (buf + data)[-4096:]
                    while b"\n" in buf:
                        regel, buf = buf.split(b"\n", 1)
                        p = lees_rmc(regel.decode("ascii", "replace"))
                        if p:
                            p["tijd"] = time.time()
                            self.fix = p
                            self.stand = "GPS heeft een positie"
                        elif b"RMC," in regel and b",V," in regel:
                            self.stand = "GPS gevonden, nog geen positie (buiten, vrij zicht op de lucht)"
            except OSError as e:
                self.stand = f"GPS-verbinding weg: {e}"
                self.fix = None
                time.sleep(3)
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# APRS
# ---------------------------------------------------------------------------

def aprs_positie(lat, lon, symbool=">", commentaar="", koers=None, kmh=None):
    """APRS-positie zonder tijd, met berichten ('='): '=5212.34N/00612.34E>088/036AX25Chat'."""
    la, lo = abs(lat), abs(lon)
    lat_t = f"{int(la):02d}{(la - int(la)) * 60:05.2f}{'N' if lat >= 0 else 'S'}"
    lon_t = f"{int(lo):03d}{(lo - int(lo)) * 60:05.2f}{'E' if lon >= 0 else 'W'}"
    if lat_t[2:4] == "60":                     # afronden kan 60,00 minuten geven
        lat_t = f"{int(la) + 1:02d}00.00{lat_t[-1]}"
    if lon_t[3:5] == "60":
        lon_t = f"{int(lo) + 1:03d}00.00{lon_t[-1]}"
    ext = ""
    if koers is not None and kmh is not None and kmh >= TRAAG_KMH:
        ext = f"{(round(koers) % 360) or 360:03d}/{min(999, round(kmh / 1.852)):03d}"
    return f"={lat_t}/{lon_t}{symbool}{ext}{commentaar}"


def hoek(a, b):
    v = abs((a - b) % 360)
    return min(v, 360 - v)


def afstand(a, b):
    """Meters tussen twee posities (genoeg voor een paar km)."""
    dy = (a["lat"] - b["lat"]) * 111195
    dx = (a["lon"] - b["lon"]) * 111195 * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return math.hypot(dx, dy)


def moet_bakenen(nu, laatst, b, pos, vorige_koers, vorige_pos=None):
    """Is het tijd? Geeft de reden ('' = nee). Alleen als de positie verandert (of stilstaand eens per uur, als aangezet)."""
    if not laatst or vorige_pos is None:
        return "eerste"
    sinds = nu - laatst
    if sinds < MIN_SEC:
        return ""
    if afstand(pos, vorige_pos) < VERPLAATST_M:
        return "stilstaand" if b.get("stilstaand") and sinds >= STIL_SEC else ""
    vast = int(b.get("interval") or 20) * 60
    if not b.get("slim") or pos.get("kmh") is None or pos["kmh"] < TRAAG_KMH:
        return "interval" if sinds >= vast else ""
    kmh = pos["kmh"]
    tempo = SNEL_SEC if kmh >= SNEL_KMH else max(SNEL_SEC, min(vast, SNEL_SEC * SNEL_KMH / kmh))
    if sinds >= tempo:
        return "rijden"
    if pos.get("koers") is not None and vorige_koers is not None and sinds >= BOCHT_MIN_SEC:
        if hoek(pos["koers"], vorige_koers) > BOCHT_MIN_GRADEN + BOCHT_HELLING / kmh:
            return "bocht"
    return ""


class Baken:
    def __init__(self, chat, gps=None, log=print, klok=time.time, start=True, verbonden=lambda: ""):
        self.chat = chat
        self.verbonden = verbonden            # roepnaam van een lopende BBS-/nodeverbinding, of ''
        self.laatst_pos = None
        self.log = log
        self.klok = klok
        self.gps = gps
        self.laatst = 0
        self.laatst_info = ""
        self.vorige_koers = None
        self.stand = ""
        self.nu_gevraagd = False
        if start:
            self.gps = gps or Gps(lambda: (instellingen().get("gps_poort") if instellingen().get("bron") == "gps" else ""), log)
            threading.Thread(target=self._run, daemon=True).start()

    def positie(self, b):
        if b.get("bron") == "gps":
            return self.gps.positie() if self.gps else None
        if b.get("lat") is None or b.get("lon") is None:
            return None
        return {"lat": b["lat"], "lon": b["lon"], "kmh": None, "koers": None}

    def stap(self):
        """Eén keer kijken of er gebakend moet worden. Geeft de verzonden info of ''."""
        b, nu = instellingen(), self.klok()
        if not b.get("aan") and not self.nu_gevraagd:
            self.stand = "Baken staat uit."
            return ""
        freq = radio.station().get("frequentie")
        if freq != rig.APRS_FREQ:
            self.stand = (f"Wacht: de set staat op {rig.mhz(freq) if freq else 'een zelf ingestelde frequentie'}. "
                          f"Het baken zendt alleen op {rig.mhz(rig.APRS_FREQ)} (Station).")
            self.nu_gevraagd = False
            return ""
        sessie = self.verbonden()
        if sessie:
            self.stand = f"Gepauzeerd: er is een verbinding met {sessie} (tabblad BBS). Na het verbreken gaat het baken verder."
            self.nu_gevraagd = False
            return ""
        pos = self.positie(b)
        if not pos:
            self.stand = ("Wacht op de GPS: " + (self.gps.stand if self.gps else "geen GPS")) if b.get("bron") == "gps" \
                else "Vul je positie in (breedte- en lengtegraad)."
            self.nu_gevraagd = False
            return ""
        reden = "nu" if self.nu_gevraagd else moet_bakenen(nu, self.laatst, b, pos, self.vorige_koers, self.laatst_pos)
        self.nu_gevraagd = False
        if not reden:
            stil = self.laatst_pos and afstand(pos, self.laatst_pos) < VERPLAATST_M
            self.stand = "Baken staat aan" + (", wacht tot je positie verandert." if stil else ".")
            return ""
        info = aprs_positie(pos["lat"], pos["lon"], b.get("symbool") or ">", (b.get("commentaar") or "")[:40],
                            pos.get("koers"), pos.get("kmh"))
        pad = [p for p in re.split(r"[ ,]+", (b.get("pad") or "").upper()) if p]
        link = self.chat.link
        link.mycall = self.chat.mijn_call()
        if not link.send_info(info, dest=ax25.TOCALL, via=pad):
            self.stand = "Baken niet verzonden: Direwolf is niet bereikbaar."
            return ""
        self.laatst, self.laatst_info, self.vorige_koers, self.laatst_pos = nu, info, pos.get("koers"), dict(pos)
        self.stand = "Baken staat aan."
        try:                                    # in de Monitor laten zien wat er de lucht in ging
            self.chat._meld("monitor", self.chat.opslag.monitor_toe(link.mycall, ax25.TOCALL, pad, info))
        except Exception:
            pass
        self.log(f"Baken ({reden}): {info}")
        return info

    def nu(self):
        self.nu_gevraagd = True
        return self.stap()

    def _run(self):
        time.sleep(20)                          # eerst Direwolf en de set laten opstarten
        while True:
            try:
                self.stap()
            except Exception as e:
                self.log(f"[-] Baken: {e}")
            time.sleep(5)


# ---------------------------------------------------------------------------
# Tabblad Radio
# ---------------------------------------------------------------------------

def lees_graad(t, maximum):
    t = (t or "").strip().replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if -maximum <= v <= maximum else None


def verwerk(f):
    """Formulier van het tabblad Radio. Geeft (fouten, melding)."""
    b = instellingen()
    fouten = []
    b["aan"] = f.get("aan") == "1"
    b["bron"] = "handmatig" if f.get("bron") == "handmatig" else "gps"
    poort = f.get("gps_poort") or ""
    if poort and poort not in kandidaat_poorten():
        fouten.append("Kies een GPS-poort uit de lijst.")
    b["gps_poort"] = poort
    lat, lon = (f.get("lat") or "").strip(), (f.get("lon") or "").strip()
    if lat or lon:
        b["lat"], b["lon"] = lees_graad(lat, 90), lees_graad(lon, 180)
        if b["lat"] is None or b["lon"] is None:
            fouten.append("Positie: breedte- en lengtegraad als getal, bijv. 52,1234 en 6,1234.")
    else:
        b["lat"] = b["lon"] = None
    if b["aan"] and b["bron"] == "handmatig" and b["lat"] is None:
        fouten.append("Vul je positie in, of kies GPS.")
    if b["aan"] and b["bron"] == "gps" and not poort:
        fouten.append("Kies de poort van de GPS (of gebruik Zoek GPS).")
    try:
        b["interval"] = int(f.get("interval") or 20)
    except ValueError:
        b["interval"] = 20
    if b["interval"] not in INTERVALLEN:
        b["interval"] = 20
    b["slim"] = f.get("slim") == "1"
    b["stilstaand"] = f.get("stilstaand") == "1"
    b["symbool"] = f.get("symbool") if f.get("symbool") in dict(SYMBOLEN) else ">"
    b["commentaar"] = re.sub(r"[^\w \-./:()@#,+]", "", (f.get("commentaar") or "").strip())[:40]
    pad = [x for x in re.split(r"[ ,]+", (f.get("pad") or "").strip().upper()) if x]
    if len(pad) > 2 or not all(radio.ROEPNAAM_RE.match(x) for x in pad):
        fouten.append("Pad: bijv. WIDE1-1,WIDE2-1 (hoogstens twee), of leeg.")
    b["pad"] = ",".join(pad)
    if fouten:
        return fouten, None
    s = radio.station()
    s["baken"] = b
    radio.schrijf(radio.STATION_FILE, s)
    return [], "Baken opgeslagen." + ("" if b["aan"] else " (Het baken staat uit.)")


def html(verborgen, baken=None):
    e = radio.e
    b = instellingen()
    poorten = kandidaat_poorten()
    opties = '<option value="">(geen)</option>' + "".join(
        f'<option value="{e(p)}"{" selected" if p == b["gps_poort"] else ""}>{e(usb.korte_naam(p))}</option>' for p in poorten)
    if b["gps_poort"] and b["gps_poort"] not in poorten:
        opties += f'<option value="{e(b["gps_poort"])}" selected>{e(usb.korte_naam(b["gps_poort"]))} (niet aangesloten)</option>'
    sym = "".join(f'<option value="{e(k)}"{" selected" if k == b["symbool"] else ""}>{e(n)}</option>' for k, n in SYMBOLEN)
    iv = "".join(f'<option value="{m}"{" selected" if m == b["interval"] else ""}>elke {m} minuten</option>' for m in INTERVALLEN)
    stand, laatst = "", ""
    if baken:
        stand = baken.stand or ""
        if baken.gps and b.get("bron") == "gps":
            p = baken.gps.positie()
            stand += f" {baken.gps.stand}" + (f": {p['lat']:.5f}, {p['lon']:.5f}, {p['kmh']:.0f} km/h" if p else ".")
        if baken.laatst:
            laatst = (f"<p class='uitleg mono'>Laatste baken om {time.strftime('%H:%M', time.localtime(baken.laatst))}: "
                      f"{e(baken.laatst_info)}</p>")
    lat = "" if b["lat"] is None else f'{b["lat"]:.5f}'.replace(".", ",")
    lon = "" if b["lon"] is None else f'{b["lon"]:.5f}'.replace(".", ",")
    return f"""<section><h2>APRS-baken</h2><p class="uitleg">Zendt je positie op {rig.mhz(rig.APRS_FREQ)} (FM-D, 1200 baud),
zodat je op kaarten als aprs.fi verschijnt. Alleen als je positie verandert, alleen als Station op {rig.mhz(rig.APRS_FREQ)}
staat, en niet tijdens een BBS-verbinding.</p>
<p class="melding {'ok' if b['aan'] and 'aan' in stand else 'let'}" style="margin:0 0 8px">{e(stand.strip() or ('Baken staat aan.' if b['aan'] else 'Baken staat uit.'))}</p>{laatst}
<form method="post" action="/baken">{verborgen}
<label><input type="checkbox" name="aan" value="1"{' checked' if b['aan'] else ''} style="width:auto"> Baken aan</label>
<div class="rij"><div><label>Positie uit</label><select name="bron">
<option value="gps"{' selected' if b['bron'] == 'gps' else ''}>GPS-ontvanger (USB)</option>
<option value="handmatig"{' selected' if b['bron'] == 'handmatig' else ''}>Vaste positie (hieronder)</option></select></div>
<div><label>GPS-poort <small>of gebruik Zoek GPS</small></label><select name="gps_poort">{opties}</select></div></div>
<div class="rij"><div><label>Breedtegraad <small>vaste positie, bijv. 52,1234</small></label><input type="text" name="lat" value="{lat}"></div>
<div><label>Lengtegraad <small>bijv. 6,1234</small></label><input type="text" name="lon" value="{lon}"></div></div>
<div class="rij"><div><label>Hoe vaak <small>tijdens het rijden</small></label><select name="interval">{iv}</select></div>
<div><label>Symbool <small>op de kaart</small></label><select name="symbool">{sym}</select></div></div>
<label><input type="checkbox" name="slim" value="1"{' checked' if b['slim'] else ''} style="width:auto"> Vaker tijdens het rijden
<small>(tot elke 3 minuten bij 90 km/h, en na een bocht)</small></label>
<label><input type="checkbox" name="stilstaand" value="1"{' checked' if b['stilstaand'] else ''} style="width:auto"> Ook stilstaand eens per uur
<small>(anders alleen als je positie verandert)</small></label>
<div class="rij"><div><label>Commentaar <small>max. 40 tekens</small></label><input type="text" name="commentaar" maxlength="40" value="{e(b['commentaar'])}"></div>
<div><label>Pad <small>digipeaters</small></label><input type="text" name="pad" value="{e(b['pad'])}" placeholder="WIDE1-1,WIDE2-1"></div></div>
<div class="balk"><button type="submit" name="actie" value="opslaan">Opslaan</button>
<button type="submit" name="actie" value="zoek" class="licht">Zoek GPS</button>
<button type="submit" name="actie" value="nu" class="licht">Nu een baken zenden</button></div></form></section>"""
