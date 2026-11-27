#!/usr/bin/env python3
"""
ax25chat_web.py - webserver van AX25Chat op de Pi.

Open via de wifi-hotspot van de Pi:   http://10.42.0.1
  Chat      (stap 2: berichten lezen en sturen; nu nog een overzicht)
  Kaart     gehoorde stations met een APRS-positie, op de offline kaart
  Radio     station, Zoek mijn set, mijn sets, luistertest, testuitzending   (inloggen: gebruiker beheer)
  Status    diensten, hotspot, bijwerken, log van Direwolf, Pi uitschakelen    (inloggen: gebruiker beheer)

Eenmalig een wachtwoord instellen:
    python3 ax25chat_web.py --wachtwoord

Alleen standaard-Python. De opzet (formulieren, wachtwoord, CSRF) komt uit Noodnet.
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import html
import json
import os
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

import queue

import ax25chat_baken as baken
import ax25chat_bbs as bbs
import ax25chat_bbspagina as bbspagina
import ax25chat_bijwerken as bijwerken
import ax25chat_chatpagina as chatpagina
import ax25chat_kaart as kaart
import ax25chat_kaartpagina as kaartpagina
import ax25chat_locator as locator
import ax25chat_radio as radio
import ax25chat_systeem as systeem

rig = radio.rig
e = html.escape
MAP = radio.MAP
WW_FILE = os.path.join(MAP, "web_wachtwoord.json")
CSRF = secrets.token_urlsafe(24)
ZOEK_LOCK = threading.Lock()
KLAAR = None                               # PC: wordt aangeroepen met het adres zodra de webserver luistert
LOKAAL = False                             # PC zonder thuisnetwerk: alleen bereikbaar vanaf de PC zelf, geen inlog
CHAT = None                                # ax25chat_chat.Chat, gestart in main()
BBS = None                                 # ax25chat_bbs.Sessie (connected mode), gestart in main()
BAKEN = None                               # ax25chat_baken.Baken (APRS-positie), gestart in main()

CSS = """
:root{--bg:#f6f7f9;--kaart:#fff;--tekst:#1b1f24;--zacht:#5b6470;--lijn:#dde1e6;--rood:#b3261e;--rood-z:#fbe9e7;
--groen:#1e7a3a;--groen-z:#e6f4ea;--oranje:#a85d00;--oranje-z:#fff3e0;--blauw:#1d4f91;--blauw-z:#e8eef8;--knop:#1d4f91}
@media (prefers-color-scheme:dark){:root{--bg:#14171b;--kaart:#1d2126;--tekst:#e8eaed;--zacht:#a0a8b3;--lijn:#30353c;
--rood-z:#3b1d1b;--groen-z:#16301f;--oranje-z:#3a2a12;--blauw:#8ab4f8;--blauw-z:#1c2a40;--knop:#3d6fb6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tekst);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{background:#1d4f91;color:#fff;padding:12px 16px}header b{font-size:18px}header span{opacity:.85;font-size:14px;margin-left:8px}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:8px 12px;background:var(--kaart);border-bottom:1px solid var(--lijn);position:sticky;top:0;z-index:10}
nav a{padding:8px 12px;border-radius:8px;color:var(--tekst);text-decoration:none;font-weight:500}nav a.actief{background:var(--blauw-z);color:var(--blauw)}
main{max-width:880px;margin:0 auto;padding:16px}
section{background:var(--kaart);border:1px solid var(--lijn);border-radius:12px;padding:16px;margin-bottom:16px}
h2{margin:0 0 4px;font-size:18px}h3{font-size:16px;margin:12px 0 4px}p.uitleg{margin:0 0 12px;color:var(--zacht);font-size:14px}
label{display:block;font-weight:600;margin:12px 0 4px}label small{font-weight:400;color:var(--zacht)}
input[type=text],input[type=number],input[type=password],select{width:100%;padding:10px;border:1px solid var(--lijn);border-radius:8px;background:var(--bg);color:var(--tekst);font-size:16px}
.rij{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:560px){.rij{grid-template-columns:1fr}}
button,.knop{display:inline-block;padding:10px 18px;border:0;border-radius:8px;background:var(--knop);color:#fff;font-size:16px;font-weight:600;cursor:pointer;text-decoration:none}
button.licht{background:transparent;color:var(--blauw);border:1px solid var(--lijn)}button.gevaar{background:var(--rood)}
.balk{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.melding{padding:12px 14px;border-radius:8px;margin-bottom:12px}.ok{background:var(--groen-z);color:var(--groen)}
.fout{background:var(--rood-z);color:var(--rood)}.let{background:var(--oranje-z);color:var(--oranje)}
table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--lijn);vertical-align:middle}
th{color:var(--zacht);font-weight:600;font-size:13px}
.punt{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}.p-ok{background:var(--groen)}.p-uit{background:var(--rood)}.p-let{background:var(--oranje)}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;word-break:break-all}
pre{background:var(--bg);border:1px solid var(--lijn);border-radius:8px;padding:10px;overflow:auto;max-height:420px;font-size:12.5px;white-space:pre-wrap}
details summary{cursor:pointer;color:var(--blauw);font-weight:600;margin:8px 0}
html{scroll-padding-top:72px}
nav details.navmenu{position:relative}
nav summary{list-style:none;margin:0;padding:8px 12px;border-radius:8px;color:var(--tekst);font-weight:500;user-select:none}
nav summary::-webkit-details-marker{display:none}
nav summary::after{content:"";display:inline-block;margin-left:7px;border:5px solid transparent;border-top-color:currentColor;
border-bottom:0;vertical-align:2px}
nav summary.actief{background:var(--blauw-z);color:var(--blauw)}nav details[open]>summary{background:var(--lijn)}
nav .menulijst{position:absolute;top:calc(100% + 6px);left:0;min-width:240px;background:var(--kaart);border:1px solid var(--lijn);
border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.2);padding:6px;z-index:20}
nav .menulijst a{display:block;padding:10px 12px;font-weight:600}nav .menulijst a.sub{padding-left:30px;font-weight:400}
nav .menulijst a:hover,nav .menulijst a:focus{background:var(--blauw-z);color:var(--blauw)}
@media(max-width:560px){nav{padding:8px}nav a,nav summary{padding:8px 10px}nav details.navmenu{position:static}
nav .menulijst{left:8px;right:8px;top:100%;min-width:0}}
.laden p.uitleg{font-style:italic}
"""

PAGINAS = [("chat", "Chat"), ("bbs", "BBS"), ("kaart", "Kaart"), ("radio", "Radio"), ("status", "Status")]
# Dropdownmenu's in de balk: (id van het segment, naam, ingesprongen onder Set)
MENU = {"radio": [("station", "Station", 0), ("frequenties", "Mijn frequenties", 0), ("baken", "APRS-baken", 0),
                  ("kaarten", "Offline kaart", 0), ("set", "Set", 0), ("zoek", "Zoek mijn set", 1), ("sets", "Mijn sets", 1),
                  ("luister", "Luistertest", 1), ("test", "Testuitzending", 1), ("handmatig", "Handmatig instellen", 1)],
        "status": [("diensten", "Diensten", 0), ("hotspot", "Wifi-hotspot", 0), ("bijwerken", "Bijwerken", 0),
                   ("log", "Log van Direwolf", 0), ("pi", "Raspberry Pi", 0)]}
if not systeem.IS_PI:                      # PC: geen hotspot, geen Pi uitzetten; bijwerken gaat anders
    MENU["status"] = [x for x in MENU["status"] if x[0] not in ("hotspot", "pi")]
SEGMENTEN = {i for lijst in MENU.values() for i, _, _ in lijst}

# Voor elke pagina: menu's open/dicht, melding naar het segment waar je op Opslaan tikte, trage delen later laden
PAGINA_JS = """(function () {
  var nav = document.querySelector('nav'), menus = nav.querySelectorAll('details.navmenu');
  function ruimte() { document.documentElement.style.scrollPaddingTop = (nav.offsetHeight + 8) + 'px'; }
  ruimte(); addEventListener('resize', ruimte);
  function sluit(behalve) { menus.forEach(function (d) { if (d !== behalve) d.open = false; }); }
  menus.forEach(function (d) { d.addEventListener('toggle', function () { if (d.open) sluit(d); }); });
  document.addEventListener('click', function (ev) { if (!ev.target.closest('nav details.navmenu')) sluit(); });
  document.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') sluit(); });
  function open(id) { var el = id && document.getElementById(id); if (el && el.tagName === 'DETAILS') el.open = true; return el; }
  nav.querySelectorAll('.menulijst a').forEach(function (a) {
    a.addEventListener('click', function () { sluit(); if (a.pathname === location.pathname) open(a.hash.slice(1)); });
  });
  var bij = document.body.getAttribute('data-bij'), doel = open(bij || location.hash.slice(1)), m = document.getElementById('meld');
  if (bij && doel) {
    if (m && m.children.length) {
      var h = doel.querySelector('h2');
      if (h) h.after(m); else (doel.querySelector('section') || doel).prepend(m);
    }
    doel.scrollIntoView();
    if (history.replaceState) history.replaceState(null, '', location.pathname + '#' + bij);
  }
  var begin = Date.now();
  document.querySelectorAll('[data-deel]').forEach(function (el) {
    fetch('/deel/' + el.getAttribute('data-deel'), {credentials: 'same-origin'})
      .then(function (r) { if (!r.ok) throw r.status; return r.text(); })
      .then(function (t) {
        var d = document.getElementById(location.hash.slice(1));
        var na = d && (el.compareDocumentPosition(d) & 4), y = d && d.getBoundingClientRect().top;
        el.innerHTML = t; el.style.minHeight = '';
        if (na && Date.now() - begin < 5000) scrollBy(0, d.getBoundingClientRect().top - y);   // segment blijft staan
      })
      .catch(function () { el.innerHTML = "<p class='uitleg'>Laden lukte niet. Ververs de pagina.</p>"; });
  });
})();"""
STATISCH = {"leaflet/leaflet.js": "application/javascript; charset=utf-8", "leaflet/leaflet.css": "text/css; charset=utf-8"}


# ---------------------------------------------------------------------------
# Wachtwoord (uit Noodnet)
# ---------------------------------------------------------------------------

def wachtwoord_ok(gebruiker, ww):
    data = radio.lees(WW_FILE)
    if not data:
        return False
    try:
        zout = base64.b64decode(data["zout"])
        verwacht = base64.b64decode(data["hash"])
        poging = hashlib.pbkdf2_hmac("sha256", ww.encode(), zout, int(data.get("rondes", 200000)))
        return hmac.compare_digest(poging, verwacht) and gebruiker == data.get("gebruiker", "beheer")
    except Exception:
        return False


# Het wachtwoord controleren (200.000 rondes PBKDF2) kost op een Pi Zero bijna een seconde, en de browser stuurt het
# bij elke pagina en elk formulier opnieuw mee. Een goedgekeurde inlog onthouden we daarom 12 uur, alleen in het
# geheugen en alleen als hash. Wordt het wachtwoord gewijzigd, dan vervalt alles.
INLOG_DUUR = 12 * 3600
_INLOGS = {}


def _ww_stempel():
    try:
        return os.path.getmtime(WW_FILE)
    except OSError:
        return None


def inlog_bekend(kop):
    h = hashlib.sha256(kop.encode()).hexdigest()
    x = _INLOGS.get(h)
    return bool(x and x[0] > time.time() and x[1] == _ww_stempel())


def onthoud_inlog(kop):
    nu = time.time()
    for h in [h for h, x in _INLOGS.items() if x[0] < nu]:
        _INLOGS.pop(h, None)
    if len(_INLOGS) < 50:
        _INLOGS[hashlib.sha256(kop.encode()).hexdigest()] = (nu + INLOG_DUUR, _ww_stempel())


def stel_wachtwoord_in():
    print("Wachtwoord voor de tabbladen Radio en Status van AX25Chat (gebruiker: beheer)")
    w1 = getpass.getpass("Nieuw wachtwoord: ")
    w2 = getpass.getpass("Nog een keer: ")
    if w1 != w2 or len(w1) < 8:
        sys.exit("Niet gelijk, of korter dan 8 tekens. Niets gewijzigd.")
    zout = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", w1.encode(), zout, 200000)
    radio.schrijf(WW_FILE, {"gebruiker": "beheer", "zout": base64.b64encode(zout).decode(),
                            "hash": base64.b64encode(h).decode(), "rondes": 200000})
    os.chmod(WW_FILE, 0o600)
    print("Opgeslagen in", WW_FILE)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def versie():
    try:
        with open(os.path.join(MAP, "versie.txt"), encoding="utf-8") as f:
            return f.read().strip()[:40]
    except OSError:
        return ""


def html_nav(actief):
    uit = ""
    for p, t in PAGINAS:
        kl = "actief" if p == actief else ""
        if p in MENU:
            items = "".join(f'<a href="/{p}#{i}"{" class=sub" if sub else ""}>{e(n)}</a>' for i, n, sub in MENU[p])
            uit += f'<details class="navmenu"><summary class="{kl}">{t}</summary><div class="menulijst">{items}</div></details>'
        else:
            uit += f'<a href="/{"" if p == "chat" else p}" class="{kl}">{t}</a>'
    return uit


def pagina(actief, inhoud, melding="", bij=""):
    """bij = id van het segment (bijv. 'baken'): de melding komt daar te staan en de pagina springt erheen."""
    s = radio.station()
    nav = html_nav(actief)
    bij = bij if bij in SEGMENTEN else ""
    rn = "" if str(s.get("roepnaam")).startswith("N0CALL") else s.get("roepnaam")
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AX25Chat {e(rn or '')}</title>
<style>{CSS}</style></head><body data-mij="{e(rn or '')}"{f' data-bij="{bij}"' if bij else ''}>
<header><b>AX25Chat</b><span>{e(rn or 'roepnaam nog niet ingesteld')}{' · versie ' + e(versie()) if versie() else ''}</span></header>
<nav>{nav}</nav><main><div id="meld">{melding}</div>{inhoud}</main><script>{PAGINA_JS}</script></body></html>"""


def meldingen(ok=None, fouten=(), let=()):
    uit = f'<div class="melding ok">{e(ok)}</div>' if ok else ""
    uit += "".join(f'<div class="melding let">{e(x)}</div>' for x in let)
    return uit + "".join(f'<div class="melding fout">{e(f)}</div>' for f in fouten)


def verborgen():
    return f'<input type="hidden" name="csrf" value="{CSRF}">'


def html_chat():
    s, r = radio.station(), radio.instellingen()
    rn = s.get("roepnaam", "")
    klaar = not rn.startswith("N0CALL") and r.get("geluidskaart")
    stap = ("" if klaar else
            "<div class='melding let'>Nog niet ingesteld: ga naar <a href='/radio'>Radio</a>, vul je roepnaam in en "
            "gebruik <b>Zoek mijn set</b>.</div>")
    if radio.dienst_status(radio.DW) not in ("active", "onbekend"):
        stap += "<div class='melding fout'>Direwolf draait niet: er wordt niets verzonden of ontvangen. Zie tabblad Status.</div>"
    return chatpagina.html(stap)


def html_status():
    rijen = ""
    for d, titel in radio.DIENSTEN:
        st = radio.dienst_status(d)
        kl = "p-ok" if st == "active" else ("p-let" if st in ("activating", "reloading") else "p-uit")
        if st == "niet nodig":
            kl = "p-ok"
        tekst = {"active": "draait", "inactive": "staat uit", "failed": "GESTOPT MET FOUT", "activating": "start op...",
                 "niet nodig": "niet nodig (geen CAT)" if d == radio.RIGD else "wacht op instellingen (tabblad Radio)"}.get(st, st)
        knop = "" if d == "ax25chat-web" else (
            f"<form method='post' action='/herstart' style='margin:0'>{verborgen()}<input type='hidden' name='dienst' "
            f"value='{e(d)}'><button class='licht' type='submit'>Herstart</button></form>")
        rijen += f"<tr><td><span class='punt {kl}'></span>{e(titel)}</td><td>{e(tekst)}</td><td style='text-align:right'>{knop}</td></tr>"
    laden = radio.LADEN.format
    if not systeem.IS_PI:
        return f"""<section id="diensten"><h2>Diensten</h2><table>{rijen}</table>
{laden(deel="setkort", tekst="De set wordt uitgelezen…", hoog=40)}</section>
<section id="bijwerken"><h2>Bijwerken</h2><p class="uitleg">AX25Chat draait op deze PC vanuit
<span class="mono">{e(systeem.CODE)}</span>. Een nieuwe versie: sluit AX25Chat en haal de nieuwste versie op (zie de
procedure, deel 'AX25Chat op een PC'). Je instellingen staan apart in <span class="mono">{e(MAP)}</span> en blijven bewaard.</p></section>
<section id="log"><h2>Log van Direwolf</h2>{laden(deel="log", tekst="Het log wordt opgehaald…", hoog=200)}</section>"""
    h = radio.hotspot_status()
    hotspot = (f"<p><span class='punt {'p-ok' if h['aan'] else 'p-let'}'></span><b>{'Hotspot aan' if h['aan'] else 'Hotspot uit'}</b>"
               f"{' · ' + str(h['clients']) + ' apparaat/apparaten verbonden' if h['aan'] else ' (de Pi gebruikt een ander netwerk)'}</p>"
               f"<div class='rij'><div><label>Netwerknaam</label><div class='mono'>{e(h['ssid'] or '-')}</div></div>"
               f"<div><label>Wachtwoord</label><div class='mono'>{e(h['wachtwoord'] or '-')}</div></div></div>"
               f"<p class='uitleg' style='margin-top:10px'>Adres: http://10.42.0.1 · Android meldt \"geen internet\": "
               f"kies <i>Verbonden blijven</i>.</p>")
    return f"""<section id="diensten"><h2>Diensten</h2><table>{rijen}</table>
{laden(deel="setkort", tekst="De set wordt uitgelezen…", hoog=40)}</section>
<section id="hotspot"><h2>Wifi-hotspot</h2>{hotspot}</section>
{bijwerken.html_sectie(verborgen())}
<section id="log"><h2>Log van Direwolf</h2>{laden(deel="log", tekst="Het log wordt opgehaald…", hoog=200)}</section>
<section id="pi"><h2>Raspberry Pi</h2><p class="uitleg">Haal nooit zomaar de stroom eraf: dan kan de SD-kaart beschadigen.
Schakel de Pi hier uit en wacht tot het groene lampje niet meer knippert (± 20 seconden).</p>
<form method="post" action="/pi" class="balk" style="margin-top:0">{verborgen()}
<button type="submit" name="actie" value="uit" class="gevaar" onclick="return confirm('Pi uitschakelen?')">Pi uitschakelen</button>
<button type="submit" name="actie" value="herstart" class="licht" onclick="return confirm('Pi herstarten? Duurt ongeveer 2 minuten.')">Pi herstarten</button></form></section>"""


def html_log():
    log = systeem.logboek(radio.DW, regels=40).strip()
    log = log.replace("<0x0d><0x0a>", "\n").replace("<0x0d>", "\n").replace("<0x0a>", "\n")   # regeleinden in banners
    return f"<pre>{e(log or '(geen logregels)')}</pre>"


# Trage delen van Radio en Status: de pagina haalt ze los op (GET /deel/<naam>), zodat hij zelf meteen verschijnt
DELEN = {"set": lambda: radio.html_set_live(), "gehoord": radio.html_gehoord, "log": html_log,
         "setkort": lambda: "<table>" + radio.html_set_kort() + "</table>"}


def station_opslaan(f):
    """Station opslaan (webpagina of app) en de set en Direwolf erop zetten. Geeft (fouten, meldingen)."""
    fouten, s2 = radio.verwerk_station(f)
    if fouten:
        return fouten, []
    r = radio.instellingen()
    mis = radio.pas_toe(r, s2["roepnaam"], met_rig=False) if r.get("geluidskaart") else []
    if rig.cat_actief(r) and rig.doelfrequentie():
        mis += rig.zet_set(r)
    return [], mis


def frequenties():
    """Voor de app: de huidige frequentie en de keuzes (2 m-kanalen en Mijn frequenties)."""
    eigen = {x["hz"]: x for x in rig.eigen_frequenties()}
    keuzes = [{"hz": 0, "tekst": "Zelf instellen op de set", "eigen": False}]
    for hz in rig.frequentie_keuzes():
        if hz in eigen:
            keuzes.append({"hz": hz, "tekst": rig.eigen_tekst(eigen[hz]), "eigen": True})
        elif not any(k["hz"] == hz for k in keuzes):
            keuzes.append({"hz": hz, "tekst": rig.mhz(hz) + (" (APRS)" if hz == rig.APRS_FREQ else ""), "eigen": False})
    keuzes.sort(key=lambda k: (not k["eigen"], k["hz"]) if k["hz"] else (False, -1))
    s = radio.station()
    return {"huidig": s.get("frequentie") or 0, "tekst": rig.mhz(s.get("frequentie")), "keuzes": keuzes,
            "cat": bool(rig.cat_actief(radio.instellingen()))}


def stations_kaart(sinds=0):
    """Voor de kaart: stations met een APRS-positie, stations met alleen een locator (uit hun baken of zelf
    ingevuld) en gehoorde roepnamen zonder positie (om er een locator bij in te vullen).
    Op de kaart gaat een echte APRS-positie altijd voor een locator."""
    stations = CHAT.opslag.stations(sinds)
    gehoord, zelf = CHAT.opslag.gehoord(), locator.handmatig(radio.station())
    locs = []
    for call, loc in zelf.items():
        locs.append(dict(locator.info(loc), call=call, bron="handmatig", tekst="", tijd=gehoord.get(call)))
    for r in CHAT.opslag.locators(sinds):
        if r["call"] not in zelf and locator.info(r["locator"]):
            locs.append(dict(locator.info(r["locator"]), call=r["call"], bron="baken", tekst=r["tekst"],
                             tijd=max(r["tijd"], gehoord.get(r["call"]) or 0)))
    bekend = {x["call"] for x in stations} | {x["call"] for x in locs}
    grens = time.time() - 86400
    zonder = sorted((c for c, t in gehoord.items() if t > grens and c not in bekend and not CHAT.is_mij(c)),
                    key=lambda c: -gehoord[c])[:50]
    return {"nu": time.time(), "stations": stations, "locators": locs, "zonder": zonder}


def eigen_positie():
    """Mijn positie voor de kaart: van de GPS of de vaste positie van het baken (ook als het baken uit staat)."""
    b = baken.instellingen()
    pos = None
    if BAKEN:
        try:
            pos = BAKEN.positie(b)
        except Exception:
            pos = None
    if not pos and b.get("lat") is not None and b.get("lon") is not None:
        pos = {"lat": b["lat"], "lon": b["lon"]}
    if not pos:
        return None
    return {"lat": round(pos["lat"], 5), "lon": round(pos["lon"], 5), "symbool": "/" + (b.get("symbool") or ">")}


def pi_actie(actie):
    if actie not in ("uit", "herstart") or not systeem.kan("uitzetten"):
        return None

    def later():
        time.sleep(2)
        systeem.pi_uitzetten(actie)
    threading.Thread(target=later, daemon=True).start()
    if actie == "uit":
        return pagina("status", bij="pi", melding=meldingen(ok="De Pi wordt uitgeschakeld. Wacht tot het groene lampje niet meer knippert "
                                             "(ongeveer 20 seconden); daarna mag de stroom eraf."))
    return pagina("status", bij="pi", melding=meldingen(ok="De Pi wordt herstart. Over ongeveer 2 minuten is alles weer actief; verbind "
                                         "dan opnieuw met de hotspot."))


# ---------------------------------------------------------------------------
# Webserver
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "AX25Chat/1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _auth(self):
        if LOKAAL:
            return True                    # alleen bereikbaar vanaf deze PC (127.0.0.1)
        kop = self.headers.get("Authorization", "")
        if kop.startswith("Basic "):
            if inlog_bekend(kop):
                return True
            try:
                g, w = base64.b64decode(kop[6:]).decode().split(":", 1)
                if wachtwoord_ok(g, w):
                    onthoud_inlog(kop)
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="AX25Chat", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Inloggen vereist (gebruiker: beheer).".encode())
        return False

    def _stuur(self, data, code=200, soort="text/html; charset=utf-8"):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        self.wfile.write(data)

    def _bestand(self, pad, soort, bewaar):
        try:
            with open(pad, "rb") as f:
                data = f.read()
        except OSError:
            return self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")
        self.send_response(200)
        self.send_header("Content-Type", soort)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", f"max-age={bewaar}")
        self.end_headers()
        self.wfile.write(data)

    def _terug(self, waar, melding="", bij=""):
        """Terug naar de pagina; met bij komt de melding bij dat segment te staan."""
        q = "&".join(x for x in (("m=" + quote(melding)) if melding else "", ("bij=" + bij) if bij else "") if x)
        self.send_response(303)
        self.send_header("Location", waar + ("?" + q if q else ""))
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        pad = url.path.strip("/")
        m = parse_qs(url.query).get("m", [""])[0]
        bij = parse_qs(url.query).get("bij", [""])[0]
        meld = ""
        if m.startswith("fout:"):
            meld = meldingen(fouten=[m[5:]])
        elif m.startswith("ok:"):
            meld = meldingen(ok=m[3:])
        if pad in ("", "chat"):
            return self._stuur(pagina("chat", html_chat(), meld))
        if pad == "bbs":
            return self._stuur(pagina("bbs", bbspagina.html(meld)))
        if pad == "kaart":
            return self._stuur(pagina("kaart", kaartpagina.html_pagina(kaart.voor_kaart()), meld))
        if pad.startswith("tegels/"):
            delen = pad.split("/")
            bestand = kaart.tegel_pad(*delen[1:4]) if len(delen) == 4 else None
            if not bestand:
                return self._stuur(b"", 404, "text/plain")
            return self._bestand(bestand, "image/png", 86400)
        if pad in STATISCH:
            return self._bestand(os.path.join(systeem.CODE, pad), STATISCH[pad], 86400)
        if pad.startswith("api/"):
            return self._api_get(pad[4:], parse_qs(url.query))
        if pad == "status.json":                      # voor de webapp (stap 3)
            s, r = radio.station(), radio.instellingen()
            return self._stuur(json.dumps({"roepnaam": s.get("roepnaam"), "frequentie": rig.doelfrequentie(),
                                           "set": r.get("set_naam"), "direwolf": radio.dienst_status(radio.DW)}),
                               soort="application/json; charset=utf-8")
        if pad not in ("radio", "status", "bijwerken", "bijwerken.json") and not pad.startswith("deel/"):
            return self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")
        if not self._auth():
            return
        if pad.startswith("deel/"):
            maak = DELEN.get(pad[5:])
            if not maak:
                return self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")
            try:
                return self._stuur(maak())
            except Exception as fout:                  # bijv. journalctl of de set antwoordt niet op tijd
                return self._stuur(f"<div class='melding fout'>Ophalen lukte niet: {e(str(fout))}</div>")
        if pad == "bijwerken":
            return self._stuur(pagina("status", bijwerken.html_voortgang(), meld))
        if pad == "bijwerken.json":
            return self._stuur(bijwerken.als_json(), soort="application/json; charset=utf-8")
        if pad == "radio":
            return self._stuur(pagina("radio", radio.html_radio(verborgen()), meld, bij))
        return self._stuur(pagina("status", html_status(), meld, bij))

    def _formulier(self):
        lengte = min(int(self.headers.get("Content-Length", 0) or 0), 100000)
        ruw = self.rfile.read(lengte).decode("utf-8", "replace")
        return {k: v[-1] for k, v in parse_qs(ruw, keep_blank_values=True).items()}

    def _json(self, data, code=200):
        return self._stuur(json.dumps(data, ensure_ascii=False), code, "application/json; charset=utf-8")

    def _api_get(self, pad, q):
        if pad == "kaart":
            return self._json(dict(kaart.voor_kaart(), download=kaart.stand_json()))
        if CHAT is None:
            return self._json({"fout": "chat niet gestart"}, 503)
        if pad == "berichten":
            try:
                sinds = float(q.get("sinds", ["0"])[0])
            except ValueError:
                sinds = 0
            nu = time.time()
            return self._json({"nu": nu, "mij": CHAT.mijn_call(), "berichten": CHAT.opslag.lijst(sinds)})
        if pad == "monitor":
            return self._json(CHAT.opslag.monitor(200))
        if pad == "frequenties":
            return self._json(frequenties())
        if pad == "stations":
            try:
                sinds = float(q.get("sinds", ["0"])[0])
            except ValueError:
                sinds = 0
            return self._json(dict(stations_kaart(sinds), mij=eigen_positie()))
        if pad == "live":
            return self._live()
        if pad == "bbs" and BBS:
            return self._json(BBS.overzicht())
        return self._json({"fout": "onbekend"}, 404)

    def _live(self):
        """Server-sent events: elk nieuw of gewijzigd bericht en elk gehoord frame, zodra het er is."""
        rij = queue.Queue(maxsize=500)

        def nieuw(soort, data):
            try:
                rij.put_nowait((soort, data))
            except queue.Full:
                pass
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        CHAT.luister(nieuw)
        try:
            self.wfile.write(b"retry: 3000\n\n")
            self.wfile.flush()
            while True:
                try:
                    soort, data = rij.get(timeout=20)
                    regel = f"event: {soort}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    regel = ": hartslag\n\n"
                self.wfile.write(regel.encode("utf-8"))
                self.wfile.flush()
        except (OSError, ValueError):
            pass
        finally:
            CHAT.stop_luisteren(nieuw)

    def _api_post(self, pad):
        # Alleen JSON: een formulier van een andere website kan dat niet sturen (geen CSRF nodig)
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._json({"fout": "alleen JSON"}, 415)
        if CHAT is None:
            return self._json({"fout": "chat niet gestart"}, 503)
        lengte = min(int(self.headers.get("Content-Length", 0) or 0), 20000)
        try:
            d = json.loads(self.rfile.read(lengte).decode("utf-8") or "{}")
        except ValueError:
            return self._json({"fout": "ongeldige JSON"}, 400)
        if pad == "berichten":
            fouten, uit = CHAT.verstuur(str(d.get("aan", "")), str(d.get("tekst", "")))
            return self._json({"fouten": fouten, "berichten": uit}, 400 if fouten else 200)
        if pad == "wis":
            return self._json({"ok": CHAT.wis(d.get("gesprek"))})
        if pad == "positie":                       # GPS van de telefoon (Android-app), voor het baken en de kaart
            fout = baken.telefoon_positie(d)
            return self._json({"fout": fout} if fout else {"ok": True, "bron": baken.instellingen().get("bron")},
                              400 if fout else 200)
        if pad == "frequentie":                    # frequentie wisselen uit de app (Mijn frequenties)
            if BAKEN and BAKEN.weg:
                return self._json({"fout": "Het baken zendt net op 144,800. Probeer het over een paar seconden opnieuw."})
            s = radio.station()
            fouten, mis = station_opslaan({"roepnaam": s.get("roepnaam", ""), "frequentie": str(d.get("hz") or 0),
                                           "pad": s.get("pad") or ""})
            if fouten:
                return self._json({"fout": "; ".join(fouten)})
            uit = frequenties()
            if mis:
                uit["fout"] = "Opgeslagen, maar " + "; ".join(mis)
            CHAT._meld("frequentie", uit)
            return self._json(uit)
        if pad == "locator":                       # locator per station zelf invullen of weghalen (tabblad Kaart)
            s = radio.station()
            fout = locator.zet_handmatig(s, d.get("call"), d.get("locator"))
            if fout:
                return self._json({"fout": fout}, 400)
            radio.schrijf(radio.STATION_FILE, s)
            CHAT._meld("locator", {"call": str(d.get("call") or "").upper()})
            return self._json({"ok": True, "handmatig": locator.handmatig(s)})
        if pad == "bbs" and BBS:
            return self._api_bbs(d)
        if pad in ("opnieuw", "stop"):
            try:
                return self._json({"ok": (CHAT.opnieuw if pad == "opnieuw" else CHAT.stop)(int(d.get("id")))})
            except (TypeError, ValueError):
                return self._json({"fout": "ongeldig id"}, 400)
        return self._json({"fout": "onbekend"}, 404)

    def _api_bbs(self, d):
        actie = d.get("actie")
        if actie in ("toevoegen", "weg"):
            if actie == "weg":
                try:
                    hz = int(d["hz"]) if d.get("hz") is not None else None
                except (TypeError, ValueError):
                    hz = None
                bbs.haal_weg(str(d.get("call", "")), hz)
                fouten = []
            else:
                fouten, _ = bbs.voeg_toe(d.get("call"), d.get("hz"), d.get("naam"))
            if fouten:
                return self._json({"fout": "; ".join(fouten)})
            CHAT._meld("bbslijst", bbs.lijst())
            return self._json({"ok": True, "lijst": bbs.lijst()})
        if actie == "verbind":
            try:
                hz = int(d.get("hz") or 0)
            except (TypeError, ValueError):
                hz = 0
            fout = BBS.verbind(d.get("call"), hz)
            call = str(d.get("call") or "").strip().upper()
            if not fout and d.get("onthoud") and call not in [x["call"] for x in bbs.lijst()]:
                if not bbs.voeg_toe(call, 0, "")[0]:                  # nieuwe roepnaam: in de keuzelijst bewaren
                    CHAT._meld("bbslijst", bbs.lijst())
        elif actie == "stuur":
            fout = BBS.stuur(d.get("tekst"))
        elif actie == "verbreek":
            fout = BBS.verbreek()
        elif actie == "wis":
            fout = BBS.wis() or ""
        else:
            return self._json({"fout": "onbekende actie"}, 400)
        return self._json({"fout": fout} if fout else {"ok": True})

    def do_POST(self):
        pad = urlparse(self.path).path.strip("/")
        if pad.startswith("api/"):
            return self._api_post(pad[4:])
        if not self._auth():
            return
        f = self._formulier()
        if not hmac.compare_digest(f.get("csrf", ""), CSRF):
            return self._terug("/radio", "fout:Formulier verlopen, probeer het opnieuw.")
        pad = urlparse(self.path).path.strip("/")
        s = radio.station()
        if pad == "station":
            fouten, mis = station_opslaan(f)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio(verborgen()), meldingen(fouten=fouten), "station"))
            return self._terug("/radio", ("fout:" + "; ".join(mis)) if mis else "ok:Station opgeslagen.", "station")
        if pad == "baken":
            if f.get("actie") == "zoek":
                gevonden = baken.zoek_gps()
                if not gevonden:
                    return self._terug("/radio", "fout:Geen GPS gevonden. Zit hij in de USB, en is het een GPS met NMEA (bijv. u-blox)?", "baken")
                b = baken.instellingen()
                b.update(gps_poort=gevonden, bron="gps")
                s["baken"] = b
                radio.schrijf(radio.STATION_FILE, s)
                return self._terug("/radio", "ok:GPS gevonden: " + radio.usb.korte_naam(gevonden) + ". Zet het baken aan en sla op.", "baken")
            fouten, melding = baken.verwerk(f)
            if fouten:
                return self._terug("/radio", "fout:" + "; ".join(fouten), "baken")
            if f.get("actie") == "nu" and BAKEN:
                info = BAKEN.nu()
                melding = ("Baken verzonden: " + info) if info else BAKEN.stand
                return self._terug("/radio", ("ok:" if info else "fout:") + melding, "baken")
            return self._terug("/radio", "ok:" + melding, "baken")
        if pad == "kaart":
            fout = kaart.start_download(f.get("plaats"), f.get("straal"), f.get("zoom"), _vaste_positie())
            return self._terug("/radio", ("fout:" + fout) if fout else "ok:Download gestart. Dit duurt een paar minuten.", "kaarten")
        if pad == "frequentie":
            fouten, melding = radio.verwerk_eigen(f)
            return self._terug("/radio", ("fout:" + "; ".join(fouten)) if fouten else "ok:" + melding, "frequenties")
        if pad == "set_zoek":
            if not ZOEK_LOCK.acquire(blocking=False):
                return self._terug("/radio", "fout:Er wordt al gezocht; wacht even.", "zoek")
            try:
                vs, meld = radio.zoek_mijn_set(s["roepnaam"])
            finally:
                ZOEK_LOCK.release()
            return self._stuur(pagina("radio", radio.html_voorstellen(vs, meld, verborgen()) + radio.html_radio(verborgen())))
        if pad == "set_kies":
            fouten, let = radio.kies_voorstel(f)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio(verborgen()), meldingen(fouten=fouten, let=let), "zoek"))
            return self._terug("/radio", "ok:Set ingesteld en bewaard. Doe nu de luistertest en een testuitzending.", "set")
        if pad == "profiel":
            actie, naam = f.get("actie"), f.get("naam", "")
            if actie == "gebruik":
                fouten, let = radio.gebruik_profiel(naam)
                return self._stuur(pagina("radio", radio.html_radio(verborgen()),
                                          meldingen(ok=None if fouten else f"{naam} in gebruik.", fouten=fouten, let=let), "sets"))
            if actie == "weg":
                radio.verwijder_profiel(naam)
                return self._terug("/radio", "ok:Profiel verwijderd.", "sets")
            fout = radio.bewaar_profiel(naam, radio.instellingen())
            if not fout:
                r = radio.instellingen()
                r["set_naam"] = naam.strip()[:40]
                radio.schrijf(radio.RADIO_FILE, r)
            return self._terug("/radio", ("fout:" + fout) if fout else "ok:Profiel bewaard.", "sets")
        if pad == "radio":
            fouten, r = radio.verwerk_handmatig(f)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio(verborgen()), meldingen(fouten=fouten), "handmatig"))
            mis = radio.pas_toe(r)
            return self._terug("/radio", ("fout:Opgeslagen, maar " + "; ".join(mis)) if mis else "ok:Opgeslagen; Direwolf is herstart.",
                               "handmatig")
        if pad == "luistertest":
            uitslag = radio.luistertest()
            return self._stuur(pagina("radio", radio.html_radio(verborgen(), luister=uitslag), bij="luister"))
        if pad == "radiotest":
            return self._stuur(pagina("radio", radio.html_radio(verborgen(), test=radio.verwerk_test(s["roepnaam"], f)), bij="test"))
        if pad == "set_nu":
            meld = rig.zet_set(radio.instellingen())
            rig.log("Set ingesteld via de webpagina" + (": " + "; ".join(meld) if meld else ""))
            return self._terug("/radio", ("fout:" + "; ".join(meld)) if meld else "ok:Set ingesteld.", "set")
        if pad == "herstart":
            ok, fout = radio.dienst("restart", f.get("dienst", ""))
            return self._terug("/status", "ok:Dienst herstart." if ok else "fout:Herstart lukte niet: " + fout, "diensten")
        if pad == "bijwerken" and systeem.kan("bijwerken_wifi"):
            uit = bijwerken.verwerk(f, verborgen())
            if uit[0] == "naar":
                return self._terug(uit[1], uit[2], "bijwerken" if uit[1] == "/status" else "")
            return self._stuur(pagina("status", uit[1]))
        if pad == "pi":
            uit = pi_actie(f.get("actie", ""))
            return self._stuur(uit) if uit else self._terug("/status", "fout:Ongeldige opdracht.", "pi")
        self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")


def _vaste_positie():
    b = baken.instellingen()
    return (b["lat"], b["lon"]) if b.get("lat") is not None and b.get("lon") is not None else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--poort", type=int, default=80 if systeem.IS_PI else 8080)
    ap.add_argument("--wachtwoord", action="store_true", help="wachtwoord instellen of wijzigen")
    ap.add_argument("--thuisnetwerk", action="store_true",
                    help="PC: ook bereikbaar voor je telefoon of de app op het thuisnetwerk (met wachtwoord)")
    args = ap.parse_args(argv)
    if args.wachtwoord:
        return stel_wachtwoord_in()
    global LOKAAL
    LOKAAL = not systeem.IS_PI and not args.thuisnetwerk
    adres = "127.0.0.1" if LOKAAL else "0.0.0.0"
    if not LOKAAL and not radio.lees(WW_FILE):
        sys.exit("Stel eerst een wachtwoord in:  python3 ax25chat_web.py --wachtwoord")
    if not systeem.IS_PI:                       # PC: Direwolf en rigctld zelf starten (op de Pi doet systemd dat)
        import atexit
        import signal
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))      # afsluiten: Direwolf en rigctld ook stoppen
        print(f"Instellingen en logboek: {MAP}", flush=True)
        for fout in systeem.start_diensten():
            print("Let op: " + fout, flush=True)
        atexit.register(systeem.stop_diensten)
    rig.start_bewaker(radio.instellingen, lambda t: print("Set: " + t, flush=True))
    global CHAT
    import ax25chat_chat
    CHAT = ax25chat_chat.open_chat(MAP, radio.station, log=lambda t: print(t, flush=True))
    r = radio.instellingen()
    if r.get("geluidskaart") and not radio.direwolf_met_agw():     # oudere direwolf.conf: AGW-poort en v2.0 erbij
        print("direwolf.conf bijwerken (AGW-poort 8000 en AX.25 v2.0 voor BBS'en)", flush=True)
        radio.pas_toe(r, met_rig=False)
    global BBS
    BBS = bbs.Sessie(radio.station, CHAT._meld, log=lambda t: print(t, flush=True), bezet=lambda: bool(BAKEN and BAKEN.weg))
    global BAKEN
    BAKEN = baken.Baken(CHAT, log=lambda t: print(t, flush=True),
                        verbonden=lambda: BBS.tegen if BBS.stand != "verbroken" else "")
    radio.NA_EIGEN.append(lambda verborgen: baken.html(verborgen, BAKEN))
    radio.NA_EIGEN.append(lambda verborgen: kaart.html_beheer(verborgen, _vaste_positie()))
    server = ThreadingHTTPServer((adres, args.poort), Handler)
    print(f"AX25Chat op http://{'localhost' if LOKAAL else adres}:{args.poort}", flush=True)
    if KLAAR:
        KLAAR(f"http://localhost:{args.poort}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if not systeem.IS_PI:
            systeem.stop_diensten()


if __name__ == "__main__":
    main()
