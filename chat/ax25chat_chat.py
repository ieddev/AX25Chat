"""
ax25chat_chat.py - de chat: berichten via AX.25 in APRS-berichtformaat (nieuw in AX25Chat, stap 2).

In de lucht (gewone, leesbare tekst; op de amateurband gaat niets versleuteld):

    PD3PAM-7>APZAXC::PA1ABC-9 :Hoi, hoor je me?{12      bericht aan PA1ABC-9, nummer 12
    PA1ABC-9>APZAXC::PD3PAM-7 :ack12                     bevestiging terug
    PD3PAM-7>APZAXC::CQ       :CQ CQ de PD3PAM           aan iedereen (zonder nummer, dus zonder bevestiging)

Dat is het berichtformaat van APRS, zodat ook APRSdroid, Kenwood- en Yaesu-sets en andere
APRS-stations de berichten kunnen lezen en beantwoorden. Andere packetstations zien het als tekst.

  - een bericht met nummer wordt herhaald tot de bevestiging binnen is (maximaal 5 keer)
  - een binnenkomend bericht aan mij krijgt een bevestiging (ook als het een herhaling is, maar
    het verschijnt maar één keer)
  - langer dan 67 tekens: opgesplitst in meer berichten
  - alles wat Direwolf hoort, komt ook in de monitor (laatste 500 frames)
  - een gehoorde APRS-positie komt in de lijst met stations, voor de kaart (een week bewaard)

Berichten staan in een SQLite-bestand (berichten.db), zodat ze een herstart overleven.
Alleen standaard-Python.
"""

import os
import re
import sqlite3
import threading
import time

import ax25chat_aprs as aprs
import ax25chat_ax25 as ax25

MAX_TEKST = 67
WACHTTIJDEN = [30, 45, 60, 90, 120]       # seconden na elke poging; na de laatste: niet bevestigd
MONITOR_MAX = 500
STATION_DAGEN = 7                          # stations op de kaart: zo lang bewaard na het laatste horen
CALL_RE = re.compile(r"^[A-Z0-9]{1,6}(-([0-9]|1[0-5]))?$")


# ---------------------------------------------------------------------------
# APRS-berichtformaat
# ---------------------------------------------------------------------------

def schoon(tekst):
    """Tekens die APRS niet in een bericht toestaat vervangen ({ is het nummer, | en ~ zijn gereserveerd)."""
    tekst = re.sub(r"\s+", " ", str(tekst)).strip()
    return tekst.replace("{", "(").replace("|", "/").replace("~", "-")


def delen(tekst, n=MAX_TEKST):
    """Knipt een tekst in stukken van hoogstens n tekens, liefst tussen woorden."""
    tekst = schoon(tekst)
    uit = []
    while len(tekst) > n:
        knip = tekst.rfind(" ", 0, n + 1)
        knip = knip if knip > n // 2 else n
        uit.append(tekst[:knip].rstrip())
        tekst = tekst[knip:].lstrip()
    if tekst:
        uit.append(tekst)
    return uit


def maak_bericht(aan, tekst, nummer=None):
    """Info-veld van een APRS-bericht."""
    return f":{aan.upper():<9}:{tekst}" + (f"{{{nummer}" if nummer else "")


def maak_ack(aan, nummer):
    return f":{aan.upper():<9}:ack{nummer}"


def lees_bericht(info):
    """APRS-bericht lezen. Geeft {aan, tekst, nummer, soort ('bericht'|'ack'|'rej')} of None."""
    if isinstance(info, (bytes, bytearray)):
        info = info.decode("utf-8", "replace")
    if len(info) < 11 or info[0] != ":" or info[10] != ":":
        return None
    aan, tekst = info[1:10].strip().upper(), info[11:].rstrip("\r\n")
    m = re.match(r"^(ack|rej)([A-Za-z0-9]{1,5})(\}.*)?$", tekst)
    if m:
        return {"aan": aan, "tekst": "", "nummer": m.group(2), "soort": m.group(1)}
    nummer = None
    if "{" in tekst:
        tekst, _, rest = tekst.rpartition("{")
        nummer = rest.split("}", 1)[0][:5] or None
    return {"aan": aan, "tekst": tekst, "nummer": nummer, "soort": "bericht"}


def zelfde_call(a, b):
    """PD3PAM en PD3PAM-0 zijn dezelfde."""
    a, b = (a or "").upper().rstrip("*"), (b or "").upper().rstrip("*")
    return (a[:-2] if a.endswith("-0") else a) == (b[:-2] if b.endswith("-0") else b)


# ---------------------------------------------------------------------------
# Opslag
# ---------------------------------------------------------------------------

class Opslag:
    def __init__(self, pad):
        self.db = sqlite3.connect(pad, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock, self.db:
            self.db.executescript("""
CREATE TABLE IF NOT EXISTS berichten (
  id INTEGER PRIMARY KEY, tijd REAL, richting TEXT, van TEXT, aan TEXT, tekst TEXT,
  nummer TEXT, status TEXT, pogingen INTEGER DEFAULT 0, volgende REAL DEFAULT 0, gewijzigd REAL);
CREATE TABLE IF NOT EXISTS monitor (id INTEGER PRIMARY KEY, tijd REAL, van TEXT, aan TEXT, pad TEXT, info TEXT);
CREATE TABLE IF NOT EXISTS teller (naam TEXT PRIMARY KEY, waarde INTEGER);
CREATE TABLE IF NOT EXISTS stations (call TEXT PRIMARY KEY, tijd REAL, lat REAL, lon REAL, symbool TEXT,
  commentaar TEXT, koers INTEGER, kmh INTEGER, via TEXT, direct INTEGER);
CREATE INDEX IF NOT EXISTS berichten_gewijzigd ON berichten(gewijzigd);
""")

    def _rij(self, r):
        return dict(r) if r else None

    def nieuw_nummer(self):
        with self.lock, self.db:
            r = self.db.execute("SELECT waarde FROM teller WHERE naam='nummer'").fetchone()
            n = (r[0] if r else 0) % 99999 + 1
            self.db.execute("INSERT OR REPLACE INTO teller VALUES ('nummer', ?)", (n,))
            return str(n)

    def voeg_toe(self, **v):
        nu = time.time()
        v.setdefault("tijd", nu)
        v["gewijzigd"] = nu
        with self.lock, self.db:
            c = self.db.execute(f"INSERT INTO berichten ({','.join(v)}) VALUES ({','.join('?' * len(v))})",
                                tuple(v.values()))
            return self.bericht(c.lastrowid, _lock=False)

    def werk_bij(self, bid, **v):
        v["gewijzigd"] = time.time()
        with self.lock, self.db:
            self.db.execute(f"UPDATE berichten SET {','.join(k + '=?' for k in v)} WHERE id=?", (*v.values(), bid))
            return self.bericht(bid, _lock=False)

    def bericht(self, bid, _lock=True):
        if _lock:
            with self.lock:
                return self._rij(self.db.execute("SELECT * FROM berichten WHERE id=?", (bid,)).fetchone())
        return self._rij(self.db.execute("SELECT * FROM berichten WHERE id=?", (bid,)).fetchone())

    def zoek_uit(self, aan, nummer):
        """Mijn uitgaande bericht aan 'aan' met dit nummer (voor een ack)."""
        with self.lock:
            for r in self.db.execute("SELECT * FROM berichten WHERE richting='uit' AND nummer=? ORDER BY id DESC",
                                     (nummer,)):
                if zelfde_call(r["aan"], aan):
                    return dict(r)
        return None

    def al_ontvangen(self, van, nummer, tekst):
        with self.lock:
            return self.db.execute("SELECT 1 FROM berichten WHERE richting='in' AND van=? AND nummer=? AND tekst=? "
                                   "AND tijd > ?", (van, nummer, tekst, time.time() - 6 * 3600)).fetchone() is not None

    def te_versturen(self, nu):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                "SELECT * FROM berichten WHERE richting='uit' AND status IN ('wacht','verzonden') AND volgende<=?", (nu,))]

    def lijst(self, sinds=0, max_aantal=500):
        """Berichten die sinds 'sinds' (tijd) nieuw of gewijzigd zijn, oudste eerst."""
        with self.lock:
            rijen = self.db.execute("SELECT * FROM berichten WHERE gewijzigd > ? ORDER BY id DESC LIMIT ?",
                                    (sinds, max_aantal)).fetchall()
        return [dict(r) for r in reversed(rijen)]

    def monitor_toe(self, van, aan, pad, info):
        with self.lock, self.db:
            c = self.db.execute("INSERT INTO monitor (tijd, van, aan, pad, info) VALUES (?,?,?,?,?)",
                                (time.time(), van, aan, ",".join(pad), info))
            self.db.execute("DELETE FROM monitor WHERE id <= ?", (c.lastrowid - MONITOR_MAX,))
            return dict(self.db.execute("SELECT * FROM monitor WHERE id=?", (c.lastrowid,)).fetchone())

    def wis(self, gesprek):
        """Berichten van één gesprek ('CQ', een roepnaam) of de Monitor ('MONITOR') weghalen. Berichten die nog
        verzonden of herhaald worden blijven staan. Geeft de ids van de weggehaalde berichten."""
        with self.lock, self.db:
            if gesprek == "MONITOR":
                self.db.execute("DELETE FROM monitor")
                return []
            if gesprek == "CQ":
                waar, args = "aan='CQ'", ()
            else:
                waar, args = "((richting='uit' AND aan=?) OR (richting='in' AND van=? AND aan!='CQ'))", (gesprek, gesprek)
            waar += " AND NOT (richting='uit' AND status IN ('wacht','verzonden'))"
            ids = [r[0] for r in self.db.execute(f"SELECT id FROM berichten WHERE {waar}", args)]
            self.db.execute(f"DELETE FROM berichten WHERE {waar}", args)
            return ids

    def station_toe(self, call, pad, pos, nu=None):
        """Gehoorde positie bewaren. via: de digipeaters die het frame herhaalden (met *); direct: zonder digipeater."""
        nu = nu or time.time()
        via = [p.rstrip("*") for p in pad if p.endswith("*")]
        rij = (call.upper(), nu, pos["lat"], pos["lon"], pos["symbool"], pos["commentaar"], pos.get("koers"),
               pos.get("kmh"), ",".join(via), 0 if via else 1)
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO stations (call, tijd, lat, lon, symbool, commentaar, koers, kmh, via, "
                            "direct) VALUES (?,?,?,?,?,?,?,?,?,?)", rij)
            self.db.execute("DELETE FROM stations WHERE tijd < ?", (nu - STATION_DAGEN * 86400,))
            return dict(self.db.execute("SELECT * FROM stations WHERE call=?", (rij[0],)).fetchone())

    def stations(self, sinds=0):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM stations WHERE tijd > ? ORDER BY tijd DESC", (sinds,))]

    def monitor(self, n=200):
        with self.lock:
            return [dict(r) for r in reversed(self.db.execute(
                "SELECT * FROM monitor ORDER BY id DESC LIMIT ?", (n,)).fetchall())]


# ---------------------------------------------------------------------------
# De chat
# ---------------------------------------------------------------------------

class Chat:
    """Verbindt Direwolf (KISS) met de opslag. lees_station() geeft {'roepnaam', 'pad'} (pad: 'WIDE1-1' of '')."""

    def __init__(self, opslag, lees_station, link=None, log=print, direwolf=ax25.DIREWOLF):
        self.opslag, self.lees_station, self.log = opslag, lees_station, log
        self.luisteraars, self.llock = [], threading.Lock()
        self.link = link or ax25.KissLink(direwolf[0], direwolf[1], self.mijn_call(), self.ontvangen,
                                          log=log, met_pad=True)
        self.wek = threading.Event()
        self.gepauzeerd = False                           # True: niets versturen (de set is even weg voor het baken)

    def start(self):
        threading.Thread(target=self._herhaler, daemon=True, name="herhaler").start()

    # -- live-updates naar de webpagina's --

    def luister(self, f):
        with self.llock:
            self.luisteraars.append(f)

    def stop_luisteren(self, f):
        with self.llock:
            if f in self.luisteraars:
                self.luisteraars.remove(f)

    def _meld(self, soort, data):
        with self.llock:
            lijst = list(self.luisteraars)
        for f in lijst:
            try:
                f(soort, data)
            except Exception:
                pass

    # -- station --

    def mijn_call(self):
        call = str(self.lees_station().get("roepnaam") or "N0CALL").strip().upper()
        return call[:-2] if call.endswith("-0") else call             # PD3PAM-0 is op de lucht gewoon PD3PAM

    def _pad(self):
        return [p for p in re.split(r"[ ,]+", (self.lees_station().get("pad") or "").upper()) if p]

    def _zend(self, info):
        self.link.mycall = self.mijn_call()
        return self.link.send_info(info, dest=ax25.TOCALL, via=self._pad())

    # -- versturen --

    def verstuur(self, aan, tekst):
        """Nieuw bericht. aan = roepnaam of 'CQ'. Geeft (fouten, [berichten])."""
        aan = (aan or "").strip().upper()
        mij = self.mijn_call()
        if mij.startswith("N0CALL"):
            return ["Stel eerst je roepnaam in (tabblad Radio)."], []
        if not CALL_RE.match(aan):
            return ["Vul een roepnaam in (bijv. PA1ABC of PA1ABC-9), of CQ."], []
        stukken = delen(tekst)
        if not stukken:
            return ["Typ eerst een bericht."], []
        cq = aan == "CQ"
        uit = []
        for stuk in stukken:
            b = self.opslag.voeg_toe(richting="uit", van=mij, aan=aan, tekst=stuk,
                                     nummer=None if cq else self.opslag.nieuw_nummer(), status="wacht")
            uit.append(b)
            self._meld("bericht", b)
        self.wek.set()
        return [], uit

    def opnieuw(self, bid):
        b = self.opslag.bericht(bid)
        if not b or b["richting"] != "uit" or b["status"] not in ("mislukt", "gestopt"):
            return False
        self._meld("bericht", self.opslag.werk_bij(bid, status="wacht", pogingen=0, volgende=0))
        self.wek.set()
        return True

    def wis(self, gesprek):
        """Een berichtscherm leegmaken (alleen berichten; instellingen en frequenties blijven)."""
        gesprek = str(gesprek or "").strip().upper()
        if gesprek not in ("CQ", "MONITOR") and not CALL_RE.match(gesprek):
            return False
        ids = self.opslag.wis(gesprek)
        self._meld("gewist", {"gesprek": gesprek, "ids": ids})
        return True

    def stop(self, bid):
        """Stop met herhalen (bijv. het tegenstation is niet in de lucht). Een late bevestiging telt nog."""
        b = self.opslag.bericht(bid)
        if not b or b["richting"] != "uit" or b["status"] not in ("wacht", "verzonden"):
            return False
        self._meld("bericht", self.opslag.werk_bij(bid, status="gestopt"))
        return True

    def _herhaler(self):
        while True:
            try:
                self.verwerk_wachtrij()
            except Exception as fout:
                self.log(f"[-] herhaler: {fout}")
            self.wek.wait(3)
            self.wek.clear()

    def verwerk_wachtrij(self, nu=None):
        if self.gepauzeerd:                               # de set staat even op een andere frequentie (APRS-baken)
            return
        nu = nu or time.time()
        for b in self.opslag.te_versturen(nu):
            nu_b = self.opslag.bericht(b["id"])
            if not nu_b or nu_b["status"] not in ("wacht", "verzonden"):   # net gestopt of bevestigd
                continue
            if b["nummer"] is None:                       # CQ: één keer, geen bevestiging
                ok = self._zend(maak_bericht(b["aan"], b["tekst"]))
                self._meld("bericht", self.opslag.werk_bij(b["id"], status="cq" if ok else "wacht",
                                                          pogingen=b["pogingen"] + 1, volgende=nu + 10))
                continue
            if b["pogingen"] >= len(WACHTTIJDEN):
                self._meld("bericht", self.opslag.werk_bij(b["id"], status="mislukt"))
                continue
            ok = self._zend(maak_bericht(b["aan"], b["tekst"], b["nummer"]))
            if not ok:                                    # Direwolf niet bereikbaar: zo meteen opnieuw
                self._meld("bericht", self.opslag.werk_bij(b["id"], volgende=nu + 10))
                continue
            self._meld("bericht", self.opslag.werk_bij(b["id"], status="verzonden", pogingen=b["pogingen"] + 1,
                                                      volgende=nu + WACHTTIJDEN[b["pogingen"]]))

    # -- ontvangen --

    def ontvangen(self, van, aan, pad, info):
        """Door de KISS-verbinding aangeroepen voor elk gehoord UI-frame."""
        tekst = info.decode("utf-8", "replace") if isinstance(info, (bytes, bytearray)) else str(info)
        mij = self.mijn_call()
        if zelfde_call(van, mij):
            return                                        # mijn eigen frame, terug via een digipeater
        self._meld("monitor", self.opslag.monitor_toe(van, aan, pad, tekst))
        pos = aprs.lees_positie(info if isinstance(info, (bytes, bytearray)) else tekst, aan)
        if pos:
            self._meld("station", self.opslag.station_toe(van, pad, pos))
        b = lees_bericht(tekst)
        if not b:
            return
        if b["soort"] in ("ack", "rej"):
            if zelfde_call(b["aan"], mij):
                eigen = self.opslag.zoek_uit(van, b["nummer"])
                if eigen and eigen["status"] in ("wacht", "verzonden", "gestopt", "mislukt"):
                    self._meld("bericht", self.opslag.werk_bij(
                        eigen["id"], status="bevestigd" if b["soort"] == "ack" else "geweigerd"))
            return
        voor_mij = zelfde_call(b["aan"], mij)
        cq = b["aan"] in ("CQ", "ALL", "QST") or b["aan"].startswith("BLN")
        if not (voor_mij or cq):
            return                                        # bericht tussen anderen: alleen in de monitor
        if voor_mij and b["nummer"]:
            self._zend(maak_ack(van, b["nummer"]))
            if self.opslag.al_ontvangen(van, b["nummer"], b["tekst"]):
                return                                    # herhaling: wel opnieuw bevestigd, niet dubbel tonen
        self._meld("bericht", self.opslag.voeg_toe(richting="in", van=van.upper(), aan="CQ" if cq else mij,
                                                  tekst=b["tekst"], nummer=b["nummer"], status="ontvangen"))


def open_chat(map_, lees_station, log=print):
    opslag = Opslag(os.path.join(map_, "berichten.db"))
    chat = Chat(opslag, lees_station, log=log)
    chat.start()
    return chat
