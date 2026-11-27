"""
ax25chat_bbs.py - connected mode: verbinden met een bestaande BBS (of een ander station) via Direwolf (AGW).

AX25Chat is geen BBS: het is een terminal naar een BBS. Er is steeds één verbinding tegelijk.

- Sessie: verbinden, verbreken, tekst sturen en ontvangen. De stand (verbroken, verbinden, verbonden,
  verbreken) en elke nieuwe regel gaan live naar de pagina (server-sent event 'bbs').
- Mijn BBS'en: een eigen lijst (roepnaam, frequentie uit de frequentielijst, naam) in station.json.
  Mode en snelheid komen van de frequentie (Mijn frequenties of de voorkeuzelijst), net als bij Station.
"""

import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gemeenschappelijk"))

import ax25chat_agw as agw  # noqa: E402
import ax25chat_radio as radio  # noqa: E402
import ax25chat_rig as rig  # noqa: E402

CALL_RE = re.compile(r"^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")
MAX_BBS = 20
MAX_REGELS = 1500                 # zoveel stukken tekst onthoudt de pagina van de sessie
MAX_TEKST = 250                   # één invoerregel
TIJD_VERBREKEN = 40               # zoveel seconden wachten op het antwoord op verbreken


def zelfde(a, b):
    """PD4R en PD4R-0 zijn hetzelfde station."""
    def n(x):
        x = (x or "").upper()
        return x[:-2] if x.endswith("-0") else x
    return n(a) == n(b)


def tekst_van(data):
    """Bytes van de BBS -> tekst. UTF-8 als dat kan, anders Latin-1 (oudere BBS'en)."""
    data = data.rstrip(b"\0")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# ---------------------------------------------------------------------------
# Mijn BBS'en
# ---------------------------------------------------------------------------

def lijst():
    """[{'call', 'hz', 'naam', 'tekst'}]; hz 0 = frequentie niet wisselen."""
    s = radio.station()
    uit = []
    for x in s.get("bbs") or []:
        try:
            call, hz = str(x["call"]).upper(), int(x.get("hz") or 0)
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
        if CALL_RE.match(call):
            uit.append({"call": call, "hz": hz, "naam": str(x.get("naam") or "")[:30]})
    for x in uit:
        x["id"] = f'{x["call"]}@{x["hz"]}'           # dezelfde roepnaam kan op meer frequenties staan (node op 2 m en 70 cm)
        e = rig.instelling(x["hz"]) if x["hz"] else None
        x["tekst"] = (rig.eigen_tekst(dict(e, naam="")) if e else rig.mhz(x["hz"])) if x["hz"] else "huidige frequentie"
    return uit


def voeg_toe(call, hz, naam):
    """Geeft (fouten, melding)."""
    call = agw.schoon_call(call)
    if not CALL_RE.match(call):
        return ["Roepnaam van de BBS: bijv. PD4R-1."], None
    try:
        hz = int(hz or 0)
    except (TypeError, ValueError):
        hz = -1
    if hz and hz not in rig.frequentie_keuzes():
        return ["Kies een frequentie uit de lijst."], None
    naam = re.sub(r"[^\w \-./]", "", str(naam or "").strip())[:30]
    oud = [x for x in lijst() if (x["call"], x["hz"]) != (call, hz)]      # zelfde roepnaam én frequentie: vervangen
    if len(oud) >= MAX_BBS:
        return [f"Hoogstens {MAX_BBS} BBS'en; haal er eerst een weg."], None
    s = radio.station()
    s["bbs"] = [{"call": x["call"], "hz": x["hz"], "naam": x["naam"]} for x in oud] + [{"call": call, "hz": hz, "naam": naam}]
    radio.schrijf(radio.STATION_FILE, s)
    return [], f"{call} toegevoegd."


def haal_weg(call, hz=None):
    """Haalt deze BBS weg; zonder hz alle regels met deze roepnaam."""
    call = str(call).upper()
    s = radio.station()
    s["bbs"] = [{"call": x["call"], "hz": x["hz"], "naam": x["naam"]} for x in lijst()
                if not (x["call"] == call and (hz is None or x["hz"] == hz))]
    radio.schrijf(radio.STATION_FILE, s)


def wissel_frequentie(hz):
    """De set naar deze frequentie zetten, zoals Station doet. Geeft (fouten, direwolf_herstart)."""
    s, r = radio.station(), radio.instellingen()
    if not hz or s.get("frequentie") == hz:
        return [], False
    if hz not in rig.frequentie_keuzes():
        return [f"{rig.mhz(hz)} staat niet meer in de frequentielijst."], False
    oud = radio.modem(r)
    s["frequentie"] = hz
    radio.schrijf(radio.STATION_FILE, s)
    fouten, herstart = [], False
    if r.get("geluidskaart") and radio.modem(r) != oud:       # andere snelheid: Direwolf moet opnieuw starten
        fouten += radio.pas_toe(r, s["roepnaam"], met_rig=False)
        herstart = True
    if rig.cat_actief(r):
        fouten += rig.zet_set(r)
    return fouten, herstart


# ---------------------------------------------------------------------------
# De sessie
# ---------------------------------------------------------------------------

class Sessie:
    def __init__(self, lees_station, meld, wissel=wissel_frequentie, adres=agw.DIREWOLF_AGW, log=print, link=None,
                 bezet=lambda: False):
        self.bezet = bezet              # True terwijl het APRS-baken de set even op 144,800 heeft
        self.lees_station = lees_station
        self.meld = meld
        self.wissel = wissel
        self.log = log
        self.lock = threading.RLock()
        self.stand = "verbroken"
        self.tegen = ""
        self.regels = []
        self.n = 0
        self.generatie = 0              # hoe vaak de AGW-verbinding met Direwolf (opnieuw) is opgebouwd
        self.aangemeld = ""
        self.sinds = 0
        self.wisselen = False           # set wordt naar een andere frequentie gezet (Direwolf kan herstarten)
        self.terug_hz = None            # frequentie van voor de verbinding: na verbreken gaat de set daarheen terug
        self.link = link or agw.AgwLink(self._pakket, self._bij_verbinding, adres, log)
        threading.Thread(target=self._klok, daemon=True).start()

    # -- intern --

    def mijn(self):
        return agw.schoon_call(self.lees_station().get("roepnaam"))

    def _regel(self, soort, tekst):
        with self.lock:
            self.n += 1
            r = {"n": self.n, "soort": soort, "tekst": tekst, "tijd": time.time()}
            self.regels.append(r)
            del self.regels[:-MAX_REGELS]
        self.meld("bbs", dict(self.stand_info(), regel=r))

    def _zet(self, stand, info=None, tegen=None):
        with self.lock:
            self.stand = stand
            self.sinds = time.time()
            if tegen is not None:
                self.tegen = tegen
        if info:
            self._regel("info", info)
        else:
            self.meld("bbs", dict(self.stand_info(), regel=None))
        with self.lock:
            terug = self.terug_hz if stand == "verbroken" and not self.wisselen else None
            if terug is not None:
                self.terug_hz = None
        if terug is not None:                      # bijv. terug naar 144,800, zodat het APRS-baken verder kan
            threading.Thread(target=self._terug, args=(terug,), daemon=True).start()

    def _terug(self, hz):
        if not hz or hz == self.lees_station().get("frequentie"):
            return
        self._regel("info", f"Set terug naar {rig.mhz(hz)}." if hz else "Set terug naar de frequentie van ervoor.")
        try:
            fouten, _ = self.wissel(hz)
        except Exception as e:
            fouten = [str(e)]
        if fouten:
            self._regel("info", "Let op: " + "; ".join(fouten))

    def _aanmelden(self):
        mijn = self.mijn()
        if mijn and mijn != self.aangemeld:
            if self.aangemeld:
                self.link.afmelden(self.aangemeld)
            if self.link.aanmelden(mijn):
                self.aangemeld = mijn

    def _bij_verbinding(self, ok):
        with self.lock:
            if ok:
                self.generatie += 1
                self.aangemeld = ""
        if ok:
            self._aanmelden()
        elif self.stand != "verbroken" and not self.wisselen:
            self._zet("verbroken", "Direwolf is gestopt of herstart: de verbinding is weg.")

    def _pakket(self, soort, van, aan, data):
        with self.lock:
            stand, tegen = self.stand, self.tegen
        if soort == "C":
            if stand == "verbinden" and zelfde(van, tegen) or stand == "verbroken":
                self._zet("verbonden", f"Verbonden met {van}." if stand == "verbinden"
                          else f"{van} heeft verbinding met je gemaakt.", tegen=van)
            elif not zelfde(van, tegen):
                self.link.verbreek(aan, van)          # al een andere verbinding: deze niet aannemen
        elif soort == "D" and zelfde(van, tegen) and stand in ("verbonden", "verbreken"):
            self._regel("in", tekst_van(data))
        elif soort == "d" and zelfde(van, tegen) and stand != "verbroken":
            t = tekst_van(data)
            if "RETRYOUT" in t.upper():
                info = (f"Geen antwoord van {van}. Klopt de frequentie, en hoort de BBS je?" if stand == "verbinden"
                        else f"Verbinding met {van} verloren: geen antwoord meer.")
            elif stand == "verbinden":
                info = f"{van} neemt de verbinding nu niet aan (bezet?)."
            else:
                info = f"Verbinding met {van} verbroken."
            self._zet("verbroken", info)

    def _klok(self):
        while True:
            time.sleep(2)
            with self.lock:
                te_lang = self.stand == "verbreken" and time.time() - self.sinds > TIJD_VERBREKEN
            if te_lang:
                self._zet("verbroken", "Geen antwoord op verbreken; de verbinding is gesloten.")

    # -- voor de webpagina --

    def stand_info(self):
        with self.lock:
            return {"stand": self.stand, "tegen": self.tegen, "mij": self.mijn()}

    def overzicht(self):
        with self.lock:
            return dict(self.stand_info(), regels=list(self.regels), lijst=lijst())

    def verbind(self, call, hz=0, via=()):
        """Geeft een foutmelding, of '' als het verbinden begonnen is."""
        call = agw.schoon_call(call)
        if not CALL_RE.match(call):
            return "Vul een roepnaam in, bijv. PD4R-1."
        mijn = self.mijn()
        if not CALL_RE.match(mijn) or mijn.startswith("N0CALL"):
            return "Stel eerst je roepnaam in (Radio, Station)."
        if zelfde(call, mijn):
            return "Dat is je eigen roepnaam."
        if self.bezet():
            return "Even wachten: het APRS-baken zendt (een paar seconden). Probeer het zo opnieuw."
        with self.lock:
            if self.stand != "verbroken":
                return f"Er is al een verbinding met {self.tegen}. Verbreek die eerst."
            self.stand, self.tegen, self.sinds = "verbinden", call, time.time()
        if hz and hz != self.lees_station().get("frequentie"):
            self._zet("verbinden", f"Set naar {rig.mhz(hz)}...", tegen=call)
            threading.Thread(target=self._wissel_en_verbind, args=(call, hz, via), daemon=True).start()
        else:
            self._start(call, via)
        return ""

    def _wissel_en_verbind(self, call, hz, via):
        gen = self.generatie
        self.wisselen = True
        if self.terug_hz is None:
            self.terug_hz = self.lees_station().get("frequentie")
        try:
            fouten, herstart = self.wissel(hz)
        except Exception as e:
            fouten, herstart = [str(e)], False
        if fouten:
            self._regel("info", "Let op: " + "; ".join(fouten))
        if herstart:                                   # wachten tot Direwolf weer luistert
            eind = time.time() + 30
            while time.time() < eind and not (self.generatie > gen and self.link.verbonden.is_set()):
                time.sleep(0.3)
        self.wisselen = False
        with self.lock:
            stand, tegen = self.stand, self.tegen
        if stand == "verbroken":                       # intussen afgebroken: set terug naar de vorige frequentie
            self._zet("verbroken")
            return
        if stand != "verbinden" or tegen != call:
            return
        self._start(call, via)

    def _start(self, call, via):
        if not self.link.verbonden.is_set():
            self._zet("verbroken", "Direwolf is niet bereikbaar (AGW-poort 8000). Kijk bij Status of Direwolf draait.")
            return
        self._aanmelden()
        if not self.link.verbind(self.mijn(), call, via):
            self._zet("verbroken", "Verbinden lukte niet: Direwolf reageert niet.")
            return
        self._zet("verbinden", f"Verbinden met {call}" + (f" via {', '.join(via)}" if via else "") + "...", tegen=call)

    def stuur(self, tekst):
        tekst = str(tekst or "").replace("\r", " ").replace("\n", " ")[:MAX_TEKST]
        with self.lock:
            if self.stand != "verbonden":
                return "Er is geen verbinding."
            tegen = self.tegen
        if not self.link.tekst(self.mijn(), tegen, tekst + "\r"):
            return "Zenden lukte niet: Direwolf reageert niet."
        self._regel("uit", tekst)
        return ""

    def verbreek(self):
        with self.lock:
            stand, tegen = self.stand, self.tegen
        if stand == "verbroken":
            return ""
        if stand == "verbinden" or stand == "verbreken":
            self.link.verbreek(self.mijn(), tegen)
            self._zet("verbroken", "Afgebroken.")
            return ""
        self.link.verbreek(self.mijn(), tegen)
        self._zet("verbreken", f"Verbinding met {tegen} verbreken...")
        return ""

    def wis(self):
        with self.lock:
            self.regels = []
        self.meld("bbs", dict(self.stand_info(), regel=None, gewist=True))
