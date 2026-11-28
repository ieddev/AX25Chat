"""
ax25chat_pcbijwerken.py - AX25Chat bijwerken op een PC (tabblad Status, blok Bijwerken).

Op de Pi gaat bijwerken via ax25chat_bijwerken.py (hotspot even uit, thuis-wifi, installeer.sh). Op een PC is het
eenvoudiger, want die heeft gewoon internet:

  Linux   AX25Chat staat als git-kopie in ~/AX25Chat (installatie/linux/installeer.sh). Controleren = git fetch;
          bijwerken = de nieuwste versie van main nemen (zoals het installatiescript). Daarna start AX25Chat
          zichzelf opnieuw, met Direwolf en rigctld.
  Windows Het programma komt uit de installer. Controleren = de nieuwste release win-v... op GitHub opzoeken;
          bijwerken = die installer downloaden en starten. AX25Chat sluit dan, de installer zet de nieuwe versie
          erover heen en start AX25Chat weer.

Je instellingen staan apart (systeem.MAP) en blijven bij bijwerken altijd bewaard.
Alleen standaard-Python.
"""

import html
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import ax25chat_systeem as systeem

e = html.escape
REPO = os.path.dirname(systeem.CODE)               # ~/AX25Chat (gemeenschappelijk/ staat daarin)
GIT = os.environ.get("AX25CHAT_GIT", "git")
RELEASES = os.environ.get("AX25CHAT_RELEASES_URL", "https://api.github.com/repos/ieddev/AX25Chat/releases?per_page=30")
AGENT = "AX25Chat-bijwerken"
_LAATST = {}                                       # uitkomst van de laatste controle (voor de pagina)
ELKE = 24 * 3600                                   # vanzelf controleren: bij het starten en daarna eens per dag


def soort():
    """'windows' (uit de installer), 'git' (Linux, git-kopie) of '' (anders: met de hand)."""
    if getattr(sys, "frozen", False) or sys.platform == "win32":
        return "windows"
    if os.path.isdir(os.path.join(REPO, ".git")):
        return "git"
    return ""


def _git(*args, timeout=60):
    return subprocess.run([GIT, "-C", REPO, *args], capture_output=True, text=True, timeout=timeout,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


def versie():
    """Versie van het programma zelf: Windows uit versie.txt bij het programma, Linux de git-commit."""
    if soort() == "git":
        r = _git("log", "-1", "--format=%h %cd", "--date=format:%Y-%m-%d", timeout=10)
        return r.stdout.strip()
    try:
        with open(os.path.join(systeem.CODE, "versie.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _nummer(tekst):
    """'0.2' of 'win-v0.2' of '0.2 (abc 2026-11-27)' -> (0, 2). Een testversie ('0.1-test.5') telt als 0.1."""
    m = re.search(r"(\d+(?:\.\d+)*)", tekst or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


# ---------------------------------------------------------------------------
# Controleren
# ---------------------------------------------------------------------------

def controleer(stil=False):
    """Is er een nieuwe versie? Geeft {"nieuw": bool, "tekst": ..., ...} en onthoudt het voor de pagina.
    stil (de controle die vanzelf gaat): lukt het niet, bijvoorbeeld zonder internet, dan blijft alles zoals het was."""
    s = soort()
    try:
        uit = _controleer_git() if s == "git" else _controleer_windows() if s == "windows" else \
            {"nieuw": False, "tekst": "Deze installatie kan niet vanzelf bijwerken. Zie de procedure."}
    except Exception as fout:
        if stil:
            return {"nieuw": False, "fout": True, "tekst": str(fout)}
        uit = {"nieuw": False, "fout": True, "tekst": f"Controleren lukte niet: {fout}"}
    uit["tijd"] = time.time()
    _LAATST.clear()
    _LAATST.update(uit)
    return uit


def internet(host="github.com", poort=443, wacht=4):
    """Is GitHub te bereiken? Zo niet, dan slaat de controle die vanzelf gaat stil over."""
    try:
        import socket
        socket.create_connection((host, poort), timeout=wacht).close()
        return True
    except OSError:
        return False


def nieuw():
    """Weet AX25Chat dat er een nieuwe versie is? (voor de balk bovenin)"""
    return bool(_LAATST.get("nieuw"))


def start_automatisch(eerst=15, elke=ELKE):
    """Op de achtergrond: na het starten en daarna eens per dag kijken of er een nieuwe versie is. Zonder internet
    gebeurt er niets. Alleen op een PC die vanzelf kan bijwerken (Linux git-kopie of Windows-installer)."""
    if not soort():
        return None

    def ronde():
        time.sleep(eerst)
        while True:
            if not _LAATST.get("nieuw") and internet():
                uit = controleer(stil=True)
                if uit.get("nieuw"):
                    print("Nieuwe versie van AX25Chat beschikbaar: " + uit.get("tekst", ""), flush=True)
            time.sleep(elke)
    t = threading.Thread(target=ronde, daemon=True, name="versiecontrole")
    t.start()
    return t


def html_balk():
    """Melding bovenin de pagina als er een nieuwe versie is."""
    if not nieuw():
        return ""
    return '<a class="nieuwversie" href="/status#bijwerken">Nieuwe versie beschikbaar · Bijwerken</a>'


def _controleer_git():
    r = _git("fetch", "-q", "origin", "main")
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:200] or "git fetch mislukt (internet?)")
    nieuw = _git("log", "--format=%h %cd  %s", "--date=format:%d-%m", "HEAD..origin/main", timeout=10).stdout.splitlines()
    if not nieuw:
        return {"nieuw": False, "tekst": "Je hebt de nieuwste versie."}
    return {"nieuw": True, "tekst": f"Er is een nieuwe versie ({len(nieuw)} wijziging{'en' if len(nieuw) > 1 else ''}).",
            "wijzigingen": nieuw[:15]}


def _releases():
    req = urllib.request.Request(RELEASES, headers={"User-Agent": AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def _controleer_windows():
    rel = [x for x in _releases() if str(x.get("tag_name", "")).startswith("win-v") and not x.get("draft")]
    if not rel:
        return {"nieuw": False, "tekst": "Er staat nog geen Windows-versie op GitHub."}
    rel.sort(key=lambda x: _nummer(x["tag_name"]), reverse=True)
    nieuwste = rel[0]
    exe = next((a for a in nieuwste.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
    huidig = _nummer(versie())
    if huidig and _nummer(nieuwste["tag_name"]) <= huidig and "-test" not in versie():
        return {"nieuw": False, "tekst": f"Je hebt de nieuwste versie ({nieuwste['tag_name'][5:]})."}
    if not exe:
        return {"nieuw": False, "tekst": f"Versie {nieuwste['tag_name'][5:]} staat klaar, maar zonder installer."}
    return {"nieuw": True, "tekst": f"Versie {nieuwste['tag_name'][5:]} staat klaar.", "url": exe["browser_download_url"],
            "naam": exe["name"], "mb": round(exe.get("size", 0) / 1e6, 1)}


# ---------------------------------------------------------------------------
# Bijwerken
# ---------------------------------------------------------------------------

def herstart_later(seconden=1.5):
    """AX25Chat opnieuw starten (na het antwoord aan de browser): Direwolf en rigctld stoppen, zelfde opdracht weer."""
    def doe():
        time.sleep(seconden)
        systeem.stop_diensten()
        os.execv(sys.executable, [sys.executable, *sys.argv])
    threading.Thread(target=doe, daemon=True).start()


def bijwerken():
    """Geeft (ok, tekst). Bij ok start AX25Chat zo meteen opnieuw (Linux) of sluit hij voor de installer (Windows)."""
    s = soort()
    try:
        if s == "git":
            return _bijwerken_git()
        if s == "windows":
            return _bijwerken_windows()
    except Exception as fout:
        return False, f"Bijwerken lukte niet: {fout}"
    return False, "Deze installatie kan niet vanzelf bijwerken. Zie de procedure."


def _bijwerken_git():
    r = _git("fetch", "-q", "origin", "main")
    if r.returncode != 0:
        return False, "Ophalen lukte niet: " + ((r.stderr or r.stdout).strip()[:200] or "internet?")
    r = _git("reset", "-q", "--hard", "origin/main", timeout=30)
    if r.returncode != 0:
        return False, "Bijwerken lukte niet: " + (r.stderr or r.stdout).strip()[:200]
    try:
        with open(os.path.join(systeem.MAP, "versie.txt"), "w", encoding="utf-8") as f:
            f.write(versie().replace("  ", " ")[:40] + "\n")
    except OSError:
        pass
    _LAATST.clear()
    herstart_later()
    return True, "Bijgewerkt naar " + versie() + ". AX25Chat start nu opnieuw; over een paar seconden is hij terug."


def _bijwerken_windows():
    info = _LAATST if _LAATST.get("url") else _controleer_windows()
    if not info.get("url"):
        return False, info.get("tekst", "Geen nieuwe versie gevonden.")
    doel = os.path.join(tempfile.gettempdir(), info.get("naam") or "AX25Chat-setup.exe")
    req = urllib.request.Request(info["url"], headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(doel + ".deel", "wb") as f:
        while True:
            blok = r.read(1 << 16)
            if not blok:
                break
            f.write(blok)
    os.replace(doel + ".deel", doel)

    def start_en_sluit():
        time.sleep(1.5)
        systeem.stop_diensten()
        os.startfile(doel)                         # de installer; die start AX25Chat na afloop weer
        os._exit(0)                                # programma dicht, zodat de installer de bestanden kan vervangen
    threading.Thread(target=start_en_sluit, daemon=True).start()
    return True, ("De installer is gedownload en start zo. AX25Chat sluit nu; volg de installer. Daarna start "
                  "AX25Chat vanzelf weer.")


# ---------------------------------------------------------------------------
# Html: blok Bijwerken op het tabblad Status
# ---------------------------------------------------------------------------

def _knop(verborgen, stap, tekst, licht=False):
    return (f'<form method="post" action="/bijwerken_pc" style="display:inline-block;margin:0 8px 8px 0">{verborgen}'
            f'<input type="hidden" name="stap" value="{stap}"><button type="submit"{" class=licht" if licht else ""}>'
            f'{e(tekst)}</button></form>')


def html_sectie(verborgen):
    s = soort()
    v = versie() or "onbekend"
    uitleg = {"git": "AX25Chat haalt de nieuwste versie van GitHub en start daarna opnieuw (ook Direwolf).",
              "windows": "AX25Chat zoekt de nieuwste Windows-versie op GitHub, downloadt de installer en start die.",
              }.get(s, "Deze installatie kan niet vanzelf bijwerken. Draai het installatiescript opnieuw (zie de procedure).")
    l = _LAATST
    uitslag = ""
    if l and (l.get("nieuw") or time.time() - l.get("tijd", 0) < 3600):
        soort_m = "fout" if l.get("fout") else ("let" if l.get("nieuw") else "ok")
        lijst = "".join(f"<li>{e(x)}</li>" for x in l.get("wijzigingen", []))
        extra = f" Download: {l['mb']} MB." if l.get("mb") else ""
        uitslag = (f'<div class="melding {soort_m}">{e(l.get("tekst", ""))}{e(extra)}'
                   f'{"<ul style=margin:6px 0 0>" + lijst + "</ul>" if lijst else ""}</div>')
    knoppen = ""
    if s:
        knoppen = _knop(verborgen, "controleer", "Controleren op nieuwe versie", licht=bool(l.get("nieuw")))
        if l.get("nieuw"):
            knoppen += _knop(verborgen, "bijwerken", "Nu bijwerken")
    return f"""<section id="bijwerken"><h2>Bijwerken</h2>
<p class="uitleg">Versie: <b>{e(v)}</b>. {e(uitleg)} Je instellingen staan apart in
<span class="mono">{e(systeem.MAP)}</span> en blijven bewaard.</p>{uitslag}{knoppen}</section>"""


def verwerk(f):
    """POST /bijwerken_pc. Geeft (soort melding 'ok'/'fout', tekst)."""
    stap = f.get("stap", "")
    if stap == "controleer":
        uit = controleer()
        return ("fout" if uit.get("fout") else "ok"), ""
    if stap == "bijwerken":
        ok, tekst = bijwerken()
        return ("ok" if ok else "fout"), tekst
    return "fout", "Onbekende opdracht."
