"""
ax25chat_over.py - het venster "Over AX25Chat" (knop Over in de menubalk): naam, versie, makers, contact,
licentie en de onderdelen van anderen die AX25Chat gebruikt. Alleen standaard-Python.
De Android-app toont hetzelfde (android/.../Over.kt); tests/test_over.py controleert dat ze gelijk blijven.
"""

import html

import ax25chat_systeem as systeem

e = html.escape

NAAM = "AX25Chat"
OMSCHRIJVING = "Packet-radio chatstation: chat, CQ, APRS-berichten en BBS'en via Direwolf."
MAKERS = "Gert de Haan (PD3PAM) en Claude.AI"
EMAIL = "ieddev@gmail.com"
GITHUB = "https://github.com/ieddev/AX25Chat"
LICENTIE = "EUPL-1.2 (European Union Public Licence)"
# (naam, wat het doet, licentie, waar)
ONDERDELEN = [
    ("Direwolf", "softwaremodem en TNC", "GPLv2", "https://github.com/wb2osz/direwolf"),
    ("Hamlib", "CAT-besturing van de set (rigctl, rigctld)", "LGPL", "https://github.com/Hamlib/Hamlib"),
    ("Leaflet", "kaart", "BSD-2", "https://leafletjs.com"),
    ("PDOK / Kadaster", "BRT-Achtergrondkaart", "CC BY 4.0", "https://www.pdok.nl"),
]


def soort_tekst():
    if systeem.IS_PI:
        return "Raspberry Pi"
    import sys
    if sys.platform == "win32":
        return "Windows"
    return "Linux-PC"


def html_dialoog(versie=""):
    """De popup (een <dialog>) die de knop Over in de menubalk opent."""
    onderdelen = "".join(f'<li><a href="{e(url)}" target="_blank" rel="noopener" data-extern>{e(n)}</a>: {e(wat)} ({e(lic)})</li>'
                         for n, wat, lic, url in ONDERDELEN)
    return f"""<dialog id="over" aria-labelledby="over_titel"><form method="dialog">
<h2 id="over_titel" style="margin:0 0 2px">{e(NAAM)}</h2>
<p class="uitleg" style="margin:0 0 10px">{e(OMSCHRIJVING)}</p>
<table class="over"><tr><th>Versie</th><td>{e(versie or "onbekend")} · {e(soort_tekst())}</td></tr>
<tr><th>Gemaakt door</th><td>{e(MAKERS)}</td></tr>
<tr><th>Contact</th><td><a href="mailto:{e(EMAIL)}" target="_blank" data-extern>{e(EMAIL)}</a></td></tr>
<tr><th>Broncode</th><td><a href="{e(GITHUB)}" target="_blank" rel="noopener" data-extern>{e(GITHUB.replace("https://", ""))}</a></td></tr>
<tr><th>Licentie</th><td>{e(LICENTIE)}</td></tr></table>
<p style="margin:12px 0 4px"><b>Met dank aan</b></p><ul class="over">{onderdelen}</ul>
<div class="balk" style="margin-top:12px"><button type="submit">Sluiten</button></div></form></dialog>"""
