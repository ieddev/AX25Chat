#!/usr/bin/env python3
"""
ax25chat_venster.py - AX25Chat op een PC in een eigen programmavenster.

Dit is een dunne schil: dezelfde webserver als op de Pi (ax25chat_web.py) draait op de achtergrond, en de
schermen verschijnen in een eigen venster met titel en pictogram in plaats van in de browser. Daarvoor
gebruikt het pywebview (Linux: GTK-WebKit of Qt, Windows: Edge WebView2).

    python3 pc/ax25chat_venster.py

Is pywebview niet geïnstalleerd, dan opent AX25Chat gewoon in de browser (zoals ax25chat_pc.py).
Draait AX25Chat al (bijvoorbeeld twee keer op het pictogram geklikt), dan opent alleen een tweede venster
naar het programma dat al draait.
Sluit je het venster, dan stopt AX25Chat, en daarmee ook Direwolf en rigctld.
"""

import json
import os
import sys
import threading
import urllib.request

os.environ.setdefault("AX25CHAT_SOORT", "pc")
HIER = os.path.dirname(os.path.abspath(__file__))
for deel in ("chat", "gemeenschappelijk"):
    sys.path.insert(0, os.path.join(HIER, "..", deel))

PICTOGRAM = os.path.join(HIER, "ax25chat.png")
TITEL = "AX25Chat"


def draait_al(poort):
    """Antwoordt er al een AX25Chat op deze poort?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{poort}/status.json", timeout=2) as r:
            return "roepnaam" in json.loads(r.read().decode())
    except Exception:
        return False


def poort_uit(args):
    if "--poort" in args:
        try:
            return int(args[args.index("--poort") + 1])
        except (IndexError, ValueError):
            pass
    return 8080


def main():
    args = sys.argv[1:]
    if "--wachtwoord" in args or "-h" in args or "--help" in args:
        import ax25chat_web as web
        return web.main(args)
    try:
        import webview
    except ImportError:
        print("pywebview is niet geïnstalleerd: AX25Chat opent in de browser.", flush=True)
        import ax25chat_pc
        return ax25chat_pc.main()

    poort = poort_uit(args)
    adres = f"http://localhost:{poort}/"
    if not draait_al(poort):
        import ax25chat_web as web
        klaar = threading.Event()
        web.KLAAR = lambda _: klaar.set()
        fout = []

        def server():
            try:
                web.main(args)
            except SystemExit as x:              # bijv. poort bezet of geen wachtwoord bij --thuisnetwerk
                fout.append(str(x.code or ""))
            except Exception as x:
                fout.append(str(x))
            klaar.set()

        draad = threading.Thread(target=server, daemon=True)
        draad.start()
        klaar.wait(60)
        if fout:
            print("AX25Chat starten lukte niet: " + " ".join(fout), file=sys.stderr)
            return 1
    else:
        draad = None
    try:
        webview.create_window(TITEL, adres, width=1000, height=820, min_size=(360, 480), text_select=True)
        try:
            webview.start(icon=PICTOGRAM)        # blijft hier tot het venster dicht is
        except TypeError:
            webview.start()                      # oudere pywebview zonder icon=
    except Exception as fout:                    # geen venster mogelijk (bijv. WebKit/WebView2 ontbreekt): browser
        print(f"Eigen venster lukte niet ({fout}); AX25Chat opent in de browser: {adres}", flush=True)
        import webbrowser
        webbrowser.open(adres)
        try:
            while draad and draad.is_alive():
                draad.join(1)
        except KeyboardInterrupt:
            pass
    finally:
        try:
            import ax25chat_systeem as systeem
            systeem.stop_diensten()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
