#!/usr/bin/env python3
"""
ax25chat_web.py - webserver van AX25Chat op de Pi.

Open via de wifi-hotspot van de Pi:   http://10.42.0.1
  Chat      (stap 2: berichten lezen en sturen; nu nog een overzicht)
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
import subprocess
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
import ax25chat_radio as radio

rig = radio.rig
e = html.escape
MAP = radio.MAP
WW_FILE = os.path.join(MAP, "web_wachtwoord.json")
CSRF = secrets.token_urlsafe(24)
ZOEK_LOCK = threading.Lock()
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
"""

PAGINAS = [("chat", "Chat"), ("bbs", "BBS"), ("radio", "Radio"), ("status", "Status")]


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


def pagina(actief, inhoud, melding=""):
    s = radio.station()
    nav = "".join(f'<a href="/{"" if p == "chat" else p}" class="{"actief" if p == actief else ""}">{t}</a>' for p, t in PAGINAS)
    rn = "" if str(s.get("roepnaam")).startswith("N0CALL") else s.get("roepnaam")
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AX25Chat {e(rn or '')}</title>
<style>{CSS}</style></head><body data-mij="{e(rn or '')}">
<header><b>AX25Chat</b><span>{e(rn or 'roepnaam nog niet ingesteld')}{' · versie ' + e(versie()) if versie() else ''}</span></header>
<nav>{nav}</nav><main>{melding}{inhoud}</main></body></html>"""


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
        tekst = {"active": "draait", "inactive": "staat uit", "failed": "GESTOPT MET FOUT", "activating": "start op..."}.get(st, st)
        knop = "" if d == "ax25chat-web" else (
            f"<form method='post' action='/herstart' style='margin:0'>{verborgen()}<input type='hidden' name='dienst' "
            f"value='{e(d)}'><button class='licht' type='submit'>Herstart</button></form>")
        rijen += f"<tr><td><span class='punt {kl}'></span>{e(titel)}</td><td>{e(tekst)}</td><td style='text-align:right'>{knop}</td></tr>"
    h = radio.hotspot_status()
    hotspot = (f"<p><span class='punt {'p-ok' if h['aan'] else 'p-let'}'></span><b>{'Hotspot aan' if h['aan'] else 'Hotspot uit'}</b>"
               f"{' · ' + str(h['clients']) + ' apparaat/apparaten verbonden' if h['aan'] else ' (de Pi gebruikt een ander netwerk)'}</p>"
               f"<div class='rij'><div><label>Netwerknaam</label><div class='mono'>{e(h['ssid'] or '-')}</div></div>"
               f"<div><label>Wachtwoord</label><div class='mono'>{e(h['wachtwoord'] or '-')}</div></div></div>"
               f"<p class='uitleg' style='margin-top:10px'>Adres: http://10.42.0.1 · Android meldt \"geen internet\": "
               f"kies <i>Verbonden blijven</i>.</p>")
    log = radio._uit([radio.JOURNALCTL, "-u", radio.DW, "-n", "40", "--no-pager", "-o", "cat"], timeout=10).strip()
    log = log.replace("<0x0d><0x0a>", "\n").replace("<0x0d>", "\n").replace("<0x0a>", "\n")   # regeleinden in banners
    return f"""<section><h2>Diensten</h2><table>{rijen}{radio.html_set_kort()}</table></section>
<section><h2>Wifi-hotspot</h2>{hotspot}</section>
{bijwerken.html_sectie(verborgen())}
<section><h2>Log van Direwolf</h2><pre>{e(log or '(geen logregels)')}</pre></section>
<section><h2>Raspberry Pi</h2><p class="uitleg">Haal nooit zomaar de stroom eraf: dan kan de SD-kaart beschadigen.
Schakel de Pi hier uit en wacht tot het groene lampje niet meer knippert (± 20 seconden).</p>
<form method="post" action="/pi" class="balk" style="margin-top:0">{verborgen()}
<button type="submit" name="actie" value="uit" class="gevaar" onclick="return confirm('Pi uitschakelen?')">Pi uitschakelen</button>
<button type="submit" name="actie" value="herstart" class="licht" onclick="return confirm('Pi herstarten? Duurt ongeveer 2 minuten.')">Pi herstarten</button></form></section>"""


def pi_actie(actie):
    if actie not in ("uit", "herstart"):
        return None

    def later():
        time.sleep(2)
        subprocess.run([radio.SUDO, "-n", radio.SYSTEMCTL, "poweroff" if actie == "uit" else "reboot"],
                       capture_output=True, timeout=30)
    threading.Thread(target=later, daemon=True).start()
    if actie == "uit":
        return pagina("status", meldingen(ok="De Pi wordt uitgeschakeld. Wacht tot het groene lampje niet meer knippert "
                                             "(ongeveer 20 seconden); daarna mag de stroom eraf."))
    return pagina("status", meldingen(ok="De Pi wordt herstart. Over ongeveer 2 minuten is alles weer actief; verbind "
                                         "dan opnieuw met de hotspot."))


# ---------------------------------------------------------------------------
# Webserver
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "AX25Chat/1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _auth(self):
        kop = self.headers.get("Authorization", "")
        if kop.startswith("Basic "):
            try:
                g, w = base64.b64decode(kop[6:]).decode().split(":", 1)
                if wachtwoord_ok(g, w):
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

    def _terug(self, waar, melding=""):
        self.send_response(303)
        self.send_header("Location", waar + (("?m=" + quote(melding)) if melding else ""))
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        pad = url.path.strip("/")
        m = parse_qs(url.query).get("m", [""])[0]
        meld = ""
        if m.startswith("fout:"):
            meld = meldingen(fouten=[m[5:]])
        elif m.startswith("ok:"):
            meld = meldingen(ok=m[3:])
        if pad in ("", "chat"):
            return self._stuur(pagina("chat", html_chat(), meld))
        if pad == "bbs":
            return self._stuur(pagina("bbs", bbspagina.html(meld)))
        if pad.startswith("api/"):
            return self._api_get(pad[4:], parse_qs(url.query))
        if pad == "status.json":                      # voor de webapp (stap 3)
            s, r = radio.station(), radio.instellingen()
            return self._stuur(json.dumps({"roepnaam": s.get("roepnaam"), "frequentie": rig.doelfrequentie(),
                                           "set": r.get("set_naam"), "direwolf": radio.dienst_status(radio.DW)}),
                               soort="application/json; charset=utf-8")
        if pad not in ("radio", "status", "bijwerken", "bijwerken.json"):
            return self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")
        if not self._auth():
            return
        if pad == "bijwerken":
            return self._stuur(pagina("status", bijwerken.html_voortgang(), meld))
        if pad == "bijwerken.json":
            return self._stuur(bijwerken.als_json(), soort="application/json; charset=utf-8")
        if pad == "radio":
            return self._stuur(pagina("radio", radio.html_radio(verborgen()), meld))
        return self._stuur(pagina("status", html_status(), meld))

    def _formulier(self):
        lengte = min(int(self.headers.get("Content-Length", 0) or 0), 100000)
        ruw = self.rfile.read(lengte).decode("utf-8", "replace")
        return {k: v[-1] for k, v in parse_qs(ruw, keep_blank_values=True).items()}

    def _json(self, data, code=200):
        return self._stuur(json.dumps(data, ensure_ascii=False), code, "application/json; charset=utf-8")

    def _api_get(self, pad, q):
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
            fouten, s2 = radio.verwerk_station(f)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio(verborgen()), meldingen(fouten=fouten)))
            r = radio.instellingen()
            mis = radio.pas_toe(r, s2["roepnaam"], met_rig=False) if r.get("geluidskaart") else []
            if rig.cat_actief(r) and rig.doelfrequentie():
                mis += rig.zet_set(r)
            return self._terug("/radio", ("fout:" + "; ".join(mis)) if mis else "ok:Station opgeslagen.")
        if pad == "baken":
            if f.get("actie") == "zoek":
                gevonden = baken.zoek_gps()
                if not gevonden:
                    return self._terug("/radio", "fout:Geen GPS gevonden. Zit hij in de USB, en is het een GPS met NMEA (bijv. u-blox)?")
                b = baken.instellingen()
                b.update(gps_poort=gevonden, bron="gps")
                s["baken"] = b
                radio.schrijf(radio.STATION_FILE, s)
                return self._terug("/radio", "ok:GPS gevonden: " + radio.usb.korte_naam(gevonden) + ". Zet het baken aan en sla op.")
            fouten, melding = baken.verwerk(f)
            if fouten:
                return self._terug("/radio", "fout:" + "; ".join(fouten))
            if f.get("actie") == "nu" and BAKEN:
                info = BAKEN.nu()
                melding = ("Baken verzonden: " + info) if info else BAKEN.stand
                return self._terug("/radio", ("ok:" if info else "fout:") + melding)
            return self._terug("/radio", "ok:" + melding)
        if pad == "frequentie":
            fouten, melding = radio.verwerk_eigen(f)
            return self._terug("/radio", ("fout:" + "; ".join(fouten)) if fouten else "ok:" + melding)
        if pad == "set_zoek":
            if not ZOEK_LOCK.acquire(blocking=False):
                return self._terug("/radio", "fout:Er wordt al gezocht; wacht even.")
            try:
                vs, meld = radio.zoek_mijn_set(s["roepnaam"])
            finally:
                ZOEK_LOCK.release()
            return self._stuur(pagina("radio", radio.html_voorstellen(vs, meld, verborgen()) + radio.html_radio(verborgen())))
        if pad == "set_kies":
            fouten, let = radio.kies_voorstel(f)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio(verborgen()), meldingen(fouten=fouten, let=let)))
            return self._terug("/radio", "ok:Set ingesteld en bewaard. Doe nu de luistertest en een testuitzending.")
        if pad == "profiel":
            actie, naam = f.get("actie"), f.get("naam", "")
            if actie == "gebruik":
                fouten, let = radio.gebruik_profiel(naam)
                return self._stuur(pagina("radio", radio.html_radio(verborgen()),
                                          meldingen(ok=None if fouten else f"{naam} in gebruik.", fouten=fouten, let=let)))
            if actie == "weg":
                radio.verwijder_profiel(naam)
                return self._terug("/radio", "ok:Profiel verwijderd.")
            fout = radio.bewaar_profiel(naam, radio.instellingen())
            if not fout:
                r = radio.instellingen()
                r["set_naam"] = naam.strip()[:40]
                radio.schrijf(radio.RADIO_FILE, r)
            return self._terug("/radio", ("fout:" + fout) if fout else "ok:Profiel bewaard.")
        if pad == "radio":
            fouten, r = radio.verwerk_handmatig(f)
            if fouten:
                return self._stuur(pagina("radio", radio.html_radio(verborgen()), meldingen(fouten=fouten)))
            mis = radio.pas_toe(r)
            return self._terug("/radio", ("fout:Opgeslagen, maar " + "; ".join(mis)) if mis else "ok:Opgeslagen; Direwolf is herstart.")
        if pad == "luistertest":
            uitslag = radio.luistertest()
            return self._stuur(pagina("radio", radio.html_radio(verborgen(), luister=uitslag)))
        if pad == "radiotest":
            return self._stuur(pagina("radio", radio.html_radio(verborgen(), radio.verwerk_test(s["roepnaam"], f))))
        if pad == "set_nu":
            meld = rig.zet_set(radio.instellingen())
            rig.log("Set ingesteld via de webpagina" + (": " + "; ".join(meld) if meld else ""))
            return self._terug("/radio", ("fout:" + "; ".join(meld)) if meld else "ok:Set ingesteld.")
        if pad == "herstart":
            ok, fout = radio.dienst("restart", f.get("dienst", ""))
            return self._terug("/status", "ok:Dienst herstart." if ok else "fout:Herstart lukte niet: " + fout)
        if pad == "bijwerken":
            uit = bijwerken.verwerk(f, verborgen())
            if uit[0] == "naar":
                return self._terug(uit[1], uit[2])
            return self._stuur(pagina("status", uit[1]))
        if pad == "pi":
            uit = pi_actie(f.get("actie", ""))
            return self._stuur(uit) if uit else self._terug("/status", "fout:Ongeldige opdracht.")
        self._stuur("Niet gevonden", 404, "text/plain; charset=utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poort", type=int, default=80)
    ap.add_argument("--wachtwoord", action="store_true", help="wachtwoord instellen of wijzigen")
    args = ap.parse_args()
    if args.wachtwoord:
        return stel_wachtwoord_in()
    if not radio.lees(WW_FILE):
        sys.exit("Stel eerst een wachtwoord in:  python3 ax25chat_web.py --wachtwoord")
    rig.start_bewaker(radio.instellingen, lambda t: print("Set: " + t, flush=True))
    global CHAT
    import ax25chat_chat
    CHAT = ax25chat_chat.open_chat(MAP, radio.station, log=lambda t: print(t, flush=True))
    r = radio.instellingen()
    if r.get("geluidskaart") and not radio.direwolf_met_agw():     # Pi van voor de BBS-functie: AGW-poort aanzetten
        print("direwolf.conf bijwerken (AGW-poort 8000 voor BBS'en)", flush=True)
        radio.pas_toe(r, met_rig=False)
    global BBS
    BBS = bbs.Sessie(radio.station, CHAT._meld, log=lambda t: print(t, flush=True))
    global BAKEN
    BAKEN = baken.Baken(CHAT, log=lambda t: print(t, flush=True),
                        verbonden=lambda: BBS.tegen if BBS.stand != "verbroken" else "")
    radio.NA_EIGEN.append(lambda verborgen: baken.html(verborgen, BAKEN))
    server = ThreadingHTTPServer(("0.0.0.0", args.poort), Handler)
    print(f"AX25Chat op http://0.0.0.0:{args.poort}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
