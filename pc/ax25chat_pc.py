#!/usr/bin/env python3
"""
ax25chat_pc.py - AX25Chat op een gewone PC (Linux; Windows volgt), zonder Raspberry Pi.

    python3 pc/ax25chat_pc.py                  start AX25Chat en open het in de browser
    python3 pc/ax25chat_pc.py --geen-browser   alleen starten (open zelf http://localhost:8080)
    python3 pc/ax25chat_pc.py --thuisnetwerk   ook bereikbaar voor je telefoon/de app (met wachtwoord)
    python3 pc/ax25chat_pc.py --wachtwoord     wachtwoord instellen voor --thuisnetwerk

Wat anders is dan op de Pi:
  - AX25Chat start Direwolf en rigctld zelf (geen systemd, geen sudo) en stopt ze weer bij het afsluiten
  - instellingen en logboek staan in ~/.local/share/ax25chat (Windows: %APPDATA%\\AX25Chat)
  - geen hotspot, geen Bijwerken via thuis-wifi en geen Pi uit/herstart
  - de webpagina is standaard alleen te zien op deze PC (http://localhost:8080), zonder inloggen

Nodig op Linux:  sudo apt install direwolf libhamlib-utils alsa-utils
Uitleg: docs/PROCEDURE.md, deel 'AX25Chat op een PC'.
"""

import os
import sys

os.environ.setdefault("AX25CHAT_SOORT", "pc")
HIER = os.path.dirname(os.path.abspath(__file__))
for deel in ("chat", "gemeenschappelijk"):
    sys.path.insert(0, os.path.join(HIER, "..", deel))


def main():
    args = sys.argv[1:]
    browser = "--geen-browser" not in args
    args = [a for a in args if a != "--geen-browser"]
    import ax25chat_web as web
    if browser and "--wachtwoord" not in args:
        import threading
        import webbrowser
        web.KLAAR = lambda adres: threading.Timer(1.0, webbrowser.open, args=(adres,)).start()
    return web.main(args)


if __name__ == "__main__":
    sys.exit(main())
