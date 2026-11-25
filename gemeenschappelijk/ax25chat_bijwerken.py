"""
ax25chat_bijwerken.py - AX25Chat bijwerken vanaf de webpagina (tabblad Status). Uit Noodnet.

Een Pi Zero 2W heeft geen netwerkkabel: de hotspot gaat dan tijdelijk uit en de Pi verbindt met de
thuis-wifi (dienst ax25chat-wifi@thuiswifi, draait als root). Daar start je het bijwerken (dienst
ax25chat-bijwerken, ook als root), en na afloop gaat de hotspot na 1 minuut vanzelf weer aan.

Vangnetten (in ax25chat-wifi.sh): lukt de thuis-wifi niet, dan meteen terug naar de hotspot; na 60 minuten
gaat de hotspot hoe dan ook weer aan; na een herstart staat de hotspot altijd aan.
"""

import html
import json
import os
import re
import socket
import subprocess
import time

import ax25chat_radio as radio

e = html.escape
REPO_GIT = "https://github.com/ieddev/AX25Chat"
DIENST = "ax25chat-bijwerken"
LOG = os.environ.get("AX25CHAT_BIJWERK_LOG", "/var/log/ax25chat-bijwerken.log")           # door root geschreven
THUISWIFI_STAND = os.environ.get("AX25CHAT_THUISWIFI_STAND", "/run/ax25chat-thuiswifi")   # bestaat = hotspot tijdelijk uit
THUISWIFI_ADRES = "/var/lib/ax25chat/thuiswifi-adres"     # adres van de Pi op de thuis-wifi, vorige keer
EENMALIG = ("Werk deze Pi één keer bij via ssh met: ax25chat-bijwerken (zie de procedure). "
            "Daarna werkt deze knop.")
_GESTART = [0.0]


def _run(cmd, timeout=20, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def versie():
    try:
        with open(os.path.join(radio.MAP, "versie.txt"), encoding="utf-8") as f:
            return f.read().strip()[:40]
    except OSError:
        return ""


def bezig():
    try:
        st = _run([radio.SYSTEMCTL, "is-active", DIENST], timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return st in ("activating", "active", "reloading")


# --- wifi: hotspot of (tijdelijk) thuis-wifi ---------------------------------

def thuiswifi_naam():
    """Naam van de bekende thuis-wifi (uit de Raspberry Pi Imager of nmtui), of None."""
    try:
        uit = _run(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show"], timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for regel in uit.splitlines():
        naam, _, soort = regel.rpartition(":")
        if soort == "802-11-wireless" and naam:
            return naam.replace("\\:", ":")
    return None


def thuiswifi_actief():
    """Naam van de thuis-wifi als de hotspot bewust tijdelijk uit staat, anders None."""
    try:
        with open(THUISWIFI_STAND, encoding="utf-8") as f:
            return f.read().strip() or "thuis-wifi"
    except OSError:
        return None


def wlan_adres():
    try:
        uit = _run(["ip", "-4", "-o", "addr", "show", "dev", "wlan0"], timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for d in uit.split():
        if "/" in d and d[0].isdigit() and not d.startswith("10.42.0."):
            return d.split("/")[0]
    return None


def vorig_thuisadres():
    try:
        with open(THUISWIFI_ADRES, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _sudo_start(eenheid):
    """Start een root-dienst op de achtergrond. Geeft None of een fouttekst."""
    try:
        r = _run([radio.SUDO, "-n", radio.SYSTEMCTL, "start", "--no-block", eenheid])
    except (OSError, subprocess.SubprocessError) as ex:
        return str(ex)
    if r.returncode != 0:
        return "Dat lukte niet. " + EENMALIG + " (" + (r.stderr.strip() or r.stdout.strip())[:200] + ")"
    return None


def wifi_actie(actie):
    """'thuiswifi' of 'hotspot'. Geeft None of een fouttekst."""
    if actie not in ("thuiswifi", "hotspot"):
        return "Onbekende actie."
    return _sudo_start(f"ax25chat-wifi@{actie}")


def _adres_tekst():
    """Waar de webpagina op de thuis-wifi te vinden is (voor vóór het omschakelen)."""
    tekst = f"<b>http://{e(socket.gethostname())}.local</b>"
    vorig = vorig_thuisadres()
    if vorig:
        tekst += f" of <b>http://{e(vorig)}</b> (het adres van de vorige keer)"
    return tekst


# --- bijwerken -----------------------------------------------------------------

def _zonder_kleur(t):
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", t).replace("\r", "")


def log():
    """(regels, einde) uit het verslag; einde = None (bezig/onbekend), 0 (gelukt) of een foutcode."""
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            regels = _zonder_kleur(f.read()).splitlines()
    except OSError:
        return [], None
    einde = None
    for r in reversed(regels[-8:]):
        if r.startswith("== EINDE "):
            try:
                einde = int(r.split()[2])
            except (IndexError, ValueError):
                einde = 1
            break
    return regels, einde


def nieuwste_versie(timeout=10):
    """(hash, None) van de nieuwste versie op GitHub, of (None, fouttekst) zonder internet."""
    try:
        r = _run(["git", "ls-remote", REPO_GIT, "refs/heads/main"], timeout=timeout,
                 env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    except subprocess.TimeoutExpired:
        return None, "GitHub antwoordt niet (geen internet?)."
    except OSError:
        return None, "git ontbreekt op deze Pi."
    if r.returncode != 0 or not r.stdout.strip():
        return None, "Geen verbinding met GitHub: deze Pi heeft geen internet."
    return r.stdout.split()[0], None


def start():
    """Start het bijwerken op de achtergrond. Geeft None of een fouttekst."""
    if bezig():
        return None
    fout = _sudo_start(DIENST)
    if not fout:
        _GESTART[0] = time.time()
    return fout


def _oud_verslag():
    """Net op de knop gedrukt, maar het verslag is nog van de vorige keer (dienst nog niet gestart)."""
    if time.time() - _GESTART[0] > 60:
        return False
    try:
        return os.path.getmtime(LOG) < _GESTART[0] - 1
    except OSError:
        return True


def als_json():
    regels, einde = log()
    oud = _oud_verslag()
    b = bezig() or oud
    if oud:
        regels = ["Bijwerken wordt gestart…"]
    return json.dumps({"bezig": b, "einde": None if b else einde, "log": "\n".join(regels[-60:]),
                       "versie": versie(), "herstart": os.path.exists("/var/run/reboot-required"),
                       "thuiswifi": bool(thuiswifi_actief())}, ensure_ascii=False)


# --- HTML ---------------------------------------------------------------------

def _knop(verborgen, stap, tekst, licht=False, extra=""):
    return (f'<form method="post" action="/bijwerken" class="balk" style="margin-top:8px">{verborgen}'
            f'<input type="hidden" name="stap" value="{stap}"><button type="submit"{" class=licht" if licht else ""}'
            f'{extra}>{tekst}</button></form>')


def html_sectie(verborgen):
    """Het blok 'AX25Chat bijwerken' op het tabblad Status."""
    v = versie() or "onbekend"
    regels, einde = log()
    laatst = ""
    if bezig():
        laatst = '<p class="melding let">Bijwerken is bezig. <a href="/bijwerken">Voortgang bekijken</a></p>'
    elif einde not in (None, 0):
        laatst = '<p class="melding fout">Het laatste bijwerken is mislukt. <a href="/bijwerken">Bekijk het verslag</a></p>'
    controleer = _knop(verborgen, "controleer", "Controleren op nieuwe versie")
    tw = thuiswifi_actief()
    if tw:
        adres = wlan_adres()
        wifi = (f'<p class="melding ok"><b>Thuis-wifi actief: {e(tw)}.</b> De hotspot staat tijdelijk uit. '
                f'{("Deze Pi: <b>http://" + e(adres) + "</b>. ") if adres else ""}Controleer nu op een nieuwe versie '
                f'en werk bij. Na het bijwerken gaat de hotspot na 1 minuut vanzelf weer aan (en anders uiterlijk na '
                f'een uur).</p>{controleer}' + _knop(verborgen, "hotspot_aan", "Hotspot nu weer aanzetten", licht=True))
    else:
        naam = thuiswifi_naam()
        thuis = (f'<p class="uitleg" style="margin-top:12px">Alleen wifi (Pi Zero)? Zet de hotspot tijdelijk uit; '
                 f'de Pi gebruikt dan je thuis-wifi <b>{e(naam)}</b>.</p>'
                 + _knop(verborgen, "hotspot_uit_vraag", "Hotspot tijdelijk uitschakelen", licht=True)
                 if naam else
                 '<p class="uitleg" style="margin-top:12px">Deze Pi kent geen thuis-wifi. Voeg die toe via ssh met '
                 '<span class="mono">sudo nmtui</span>, of gebruik een netwerkkabel.</p>')
        wifi = ('<p class="uitleg">Bijwerken heeft internet nodig: je thuis-wifi of een netwerkkabel.</p>'
                + controleer + thuis)
    return (f'<section><h2>AX25Chat bijwerken</h2><p class="uitleg">Geïnstalleerd: <b>versie {e(v)}</b>. '
            f'Instellingen, sets en berichten blijven bewaard.</p>{laatst}{wifi}</section>')


def html_hotspot_uit_vraag(verborgen):
    naam = thuiswifi_naam()
    if not naam:
        return ('<section><h2>Hotspot tijdelijk uitschakelen</h2><p class="melding fout">Deze Pi kent geen thuis-wifi.</p>'
                '<p><a href="/status">Terug naar Status</a></p></section>')
    return f"""<section><h2>Hotspot tijdelijk uitschakelen</h2>
<ol>
<li>De hotspot gaat uit en de Pi verbindt met je thuis-wifi <b>{e(naam)}</b>.
Je telefoon verliest de verbinding met deze pagina.</li>
<li>Verbind je telefoon ook met <b>{e(naam)}</b> en open over een halve minuut {_adres_tekst()}.
Lukt dat niet: zoek de Pi in de lijst met apparaten van je router.</li>
<li>Op het tabblad Status zie je dan <i>Thuis-wifi actief</i>. Kies <b>Controleren op nieuwe versie</b> en daarna
<b>Nu bijwerken</b>.</li>
<li>Na het bijwerken gaat de hotspot na 1 minuut weer aan. Verbind je telefoon dan weer met de wifi van de Pi.</li>
</ol>
<p class="uitleg">Vangnet: lukt de thuis-wifi niet, dan is de hotspot binnen 2 minuten terug. Na een uur, en na een
herstart, staat de hotspot altijd weer aan. Zonder hotspot kun je niet chatten via de Pi.</p>
<form method="post" action="/bijwerken" class="balk">{verborgen}<input type="hidden" name="stap" value="hotspot_uit">
<button type="submit">Hotspot uit, thuis-wifi aan</button>
<a href="/status" style="align-self:center">Annuleren</a></form></section>"""


def html_hotspot_gaat_uit():
    naam = thuiswifi_naam() or "je thuis-wifi"
    return f"""<section><h2>Hotspot gaat uit</h2><p class="melding let"><b>De Pi schakelt nu over naar {e(naam)}.</b>
Deze pagina verliest zo de verbinding.</p>
<p>Verbind je telefoon met <b>{e(naam)}</b> en open {_adres_tekst()}.</p>
<p class="uitleg">Zie je de Pi na een minuut niet op je thuis-wifi? Verbind dan weer met de wifi van de Pi en open
http://10.42.0.1: is de thuis-wifi mislukt, dan staat de hotspot binnen 2 minuten weer aan.</p></section>"""


def html_controle(verborgen):
    """Pagina na 'Controleren': nieuwe versie ja/nee, met de knop om te starten."""
    nu = versie().split(" ")[0]
    nieuw, fout = nieuwste_versie()
    tw = thuiswifi_actief()
    if fout:
        hulp = ("Wacht een halve minuut en probeer het opnieuw; de thuis-wifi heeft misschien nog geen verbinding."
                if tw else "Zet op het tabblad Status de hotspot tijdelijk uit om je thuis-wifi te gebruiken, "
                           "of sluit een netwerkkabel aan.")
        return (f'<section><h2>AX25Chat bijwerken</h2><p class="melding fout">{e(fout)}</p>'
                f'<p class="uitleg">{hulp}</p><p><a href="/status">Terug naar Status</a></p></section>')
    zelfde = bool(nu) and nieuw.startswith(nu)
    if zelfde:
        kop = '<p class="melding ok">Je hebt al de nieuwste versie van AX25Chat.</p>'
        knop = "Toch bijwerken (ook Raspberry Pi OS)"
    else:
        kop = (f'<p class="melding let">Er is een nieuwe versie: <b>{e(nieuw[:7])}</b> '
               f'(geïnstalleerd: {e(nu or "onbekend")}).</p>')
        knop = "Nu bijwerken"
    na = " Na afloop gaat de hotspot na 1 minuut weer aan." if tw else ""
    terug = _knop(verborgen, "hotspot_aan", "Niet bijwerken, hotspot weer aanzetten", licht=True) if tw else ""
    return f"""<section><h2>AX25Chat bijwerken</h2>{kop}
<p class="uitleg">Bijwerken duurt meestal 5–15 minuten op een Pi Zero (langer als Raspberry Pi OS veel updates heeft).
Tijdens het bijwerken herstarten de diensten: chatten werkt dan even niet, en deze pagina kan een halve minuut
wegvallen. Laat de pagina open; de voortgang komt vanzelf terug.{na}</p>
<form method="post" action="/bijwerken" class="balk">{verborgen}<input type="hidden" name="stap" value="start">
<button type="submit" onclick="return confirm('AX25Chat nu bijwerken? De diensten herstarten.')">{knop}</button>
<a href="/status" style="align-self:center">Annuleren</a></form>{terug}</section>"""


def html_voortgang():
    regels, _ = log()
    return f"""<section><h2>AX25Chat bijwerken</h2><p id="bw_stand" class="melding let">Bezig met bijwerken…</p>
<p class="uitleg">Laat deze pagina open. Valt de verbinding even weg, dan probeert de pagina het vanzelf opnieuw.</p>
<pre id="bw_log">{e(chr(10).join(regels[-60:]))}</pre>
<p><a href="/status">Naar Status</a></p></section>
<script>
(function(){{
  var stand=document.getElementById('bw_stand'), log=document.getElementById('bw_log'), mis=0;
  function kijk(){{
    fetch('/bijwerken.json',{{cache:'no-store'}}).then(function(r){{return r.json();}}).then(function(d){{
      mis=0; log.textContent=d.log; log.scrollTop=log.scrollHeight;
      if(!d.bezig && d.einde===0){{ stand.className='melding ok';
        stand.innerHTML='Klaar: bijgewerkt naar versie '+d.versie+'.'+(d.herstart?' <b>Herstart de Pi</b> (Status &rarr; Pi herstarten): er is een nieuwe kernel.':'')
          +(d.thuiswifi?'<br><b>De hotspot gaat over 1 minuut weer aan.</b> Verbind je telefoon daarna weer met de wifi van de Pi (http://10.42.0.1).':'');
        return; }}
      if(!d.bezig && d.einde!==null){{ stand.className='melding fout';
        stand.textContent='Bijwerken mislukt (code '+d.einde+'). Zie het verslag hieronder; de oude versie blijft werken.'
          +(d.thuiswifi?' De thuis-wifi blijft aan: probeer het opnieuw, of zet op Status de hotspot weer aan.':''); return; }}
      stand.className='melding let'; stand.textContent='Bezig met bijwerken…';
      setTimeout(kijk,3000);
    }}).catch(function(){{ mis++; stand.className='melding let';
      stand.textContent='De webpagina herstart even… ('+mis+')'; setTimeout(kijk,4000); }});
  }}
  setTimeout(kijk,2000);
}})();
</script>"""


def verwerk(f, verborgen):
    """POST /bijwerken. Geeft ("naar", url, melding) of ('html', inhoud)."""
    stap = f.get("stap", "controleer")
    if stap == "start":
        fout = start()
        return ("naar", "/status", "fout:" + fout) if fout else ("naar", "/bijwerken", "")
    if stap == "hotspot_uit_vraag":
        return ("html", html_hotspot_uit_vraag(verborgen))
    if stap == "hotspot_uit":
        fout = wifi_actie("thuiswifi")
        return ("naar", "/status", "fout:" + fout) if fout else ("html", html_hotspot_gaat_uit())
    if stap == "hotspot_aan":
        fout = wifi_actie("hotspot")
        return ("naar", "/status", "fout:" + fout) if fout else (
            "html", '<section><h2>Hotspot gaat weer aan</h2><p class="melding ok">De hotspot gaat binnen een halve '
                    'minuut weer aan. Verbind je telefoon met de wifi van de Pi en open http://10.42.0.1.</p></section>')
    return ("html", html_controle(verborgen))
