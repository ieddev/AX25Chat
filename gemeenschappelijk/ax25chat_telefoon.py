"""
ax25chat_telefoon.py - AX25Chat op een PC bereikbaar maken voor je telefoon en de Android-app (tabblad Status,
blok Telefoon en app).

Standaard luistert AX25Chat op een PC alleen op de PC zelf (http://localhost:8080), zonder inloggen. Zet je
"Bereikbaar vanaf telefoon" aan, dan luistert hij ook op je thuisnetwerk, bijvoorbeeld http://192.168.1.50:8080.
Dan werkt het net als op een Pi in je thuis-wifi:

  - Chat, BBS, Kaart en de app werken zonder inloggen (de app stuurt geen wachtwoord mee)
  - Radio en Status vragen om de gebruiker beheer en het wachtwoord (wie op de PC zelf zit, hoeft dat niet)

De keuze staat in telefoon.json in de map met instellingen en blijft na herstarten bewaard.
Alleen standaard-Python.
"""

import html
import json
import os
import socket
import subprocess
import sys

import ax25chat_systeem as systeem

e = html.escape
BESTAND = os.path.join(systeem.MAP, "telefoon.json")


def aan():
    """Staat 'Bereikbaar vanaf telefoon' aan? (alleen op een PC; de Pi is altijd bereikbaar)"""
    try:
        with open(BESTAND, encoding="utf-8") as f:
            return bool(json.load(f).get("aan"))
    except (OSError, ValueError, AttributeError):
        return False


def zet(waarde):
    tmp = BESTAND + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"aan": bool(waarde)}, f)
        f.write("\n")
    os.replace(tmp, BESTAND)


def _prive(ip):
    """Een adres op een thuisnetwerk (192.168.x.x, 10.x.x.x, 172.16-31.x.x)."""
    try:
        a, b = (int(x) for x in ip.split(".")[:2])
    except ValueError:
        return False
    return a == 10 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31)


def adressen():
    """IPv4-adressen van deze PC op het thuisnetwerk, het meest waarschijnlijke eerst. Er gaat niets het net op:
    een UDP-'verbinding' vraagt alleen aan het systeem welk eigen adres het zou gebruiken."""
    gevonden = []

    def voeg(ip):
        if ip and _prive(ip) and ip not in gevonden:
            gevonden.append(ip)
    for doel in ("192.168.255.255", "10.255.255.255", "172.31.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((doel, 9))
                voeg(s.getsockname()[0])
        except OSError:
            pass
    if sys.platform.startswith("linux"):
        try:
            uit = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout
            for ip in uit.split():
                voeg(ip)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            voeg(ip)
    except OSError:
        pass
    return gevonden


def html_sectie(verborgen, poort, heeft_wachtwoord, staat_aan, fout=""):
    """Blok 'Telefoon en app' op het tabblad Status (alleen op een PC)."""
    if staat_aan:
        ips = adressen()
        if ips:
            regels = "".join(f"<div class='mono' style='font-size:16px'><b>{e(ip)}:{poort}</b></div>" for ip in ips)
            stand = (f"<p><span class='punt p-ok'></span><b>Aan.</b> Vul in de app bij Instellingen dit adres in:</p>"
                     f"{regels}<p class='uitleg' style='margin-top:8px'>In de browser van je telefoon: "
                     f"<span class='mono'>http://{e(ips[0])}:{poort}</span>. Telefoon en PC moeten op hetzelfde "
                     f"(wifi-)netwerk zitten.</p>")
        else:
            stand = ("<p><span class='punt p-let'></span><b>Aan</b>, maar deze PC heeft nu geen adres op een "
                     "thuisnetwerk. Zit hij aan de wifi of een netwerkkabel?</p>")
    else:
        stand = ("<p><span class='punt p-uit'></span><b>Uit.</b> AX25Chat is alleen te zien op deze PC zelf "
                 f"(<span class='mono'>http://localhost:{poort}</span>).</p>")
    if fout:
        stand = f"<div class='melding fout'>{e(fout)}</div>" + stand
    ww = ""
    if not heeft_wachtwoord:
        ww = """<p class="uitleg" style="margin-top:12px">Kies eerst een wachtwoord (minstens 8 tekens). Op je telefoon
vragen Radio en Status daarom, met de gebruiker <b>beheer</b>.</p>
<div class="rij"><div><label>Wachtwoord</label><input type="password" name="ww1" autocomplete="new-password"></div>
<div><label>Nog een keer</label><input type="password" name="ww2" autocomplete="new-password"></div></div>"""
    else:
        ww = """<details style="margin-top:8px"><summary>Wachtwoord wijzigen</summary>
<div class="rij"><div><label>Nieuw wachtwoord</label><input type="password" name="ww1" autocomplete="new-password"></div>
<div><label>Nog een keer</label><input type="password" name="ww2" autocomplete="new-password"></div></div>
<div class="balk"><button type="submit" name="actie" value="wachtwoord" class="licht">Wachtwoord opslaan</button></div>
</details>"""
    knop = ('<button type="submit" name="actie" value="uit" class="licht">Uitzetten</button>' if staat_aan else
            '<button type="submit" name="actie" value="aan">Bereikbaar maken vanaf telefoon</button>')
    windows = (" Windows vraagt de eerste keer of AX25Chat het netwerk mag gebruiken: kies <i>Toegang toestaan</i> "
               "bij privénetwerken." if sys.platform == "win32" else "")
    return f"""<section id="telefoon"><h2>Telefoon en app</h2>
<p class="uitleg">Thuis vanuit de huiskamer werken: met dit aan kun je AX25Chat op deze PC ook gebruiken vanaf je
telefoon (de Android-app of de browser), via je eigen wifi. Chat, BBS en Kaart werken dan zonder inloggen, zoals
op de Pi; Radio en Status vragen op de telefoon om het wachtwoord. Op deze PC zelf blijft alles zonder
inloggen.{windows}</p>{stand}
<form method="post" action="/telefoon">{verborgen}{ww}<div class="balk">{knop}</div></form></section>"""
