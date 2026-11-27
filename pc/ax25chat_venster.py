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


def uitvoer_naar_logboek():
    """Windows-programma zonder consolevenster: sys.stdout/stderr zijn er niet. Schrijf dan naar logboek/ax25chat.log
    in de map met instellingen, zodat er bij problemen iets na te lezen is."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    import ax25chat_systeem as systeem
    try:
        os.makedirs(systeem.LOGMAP, exist_ok=True)
        pad = os.path.join(systeem.LOGMAP, "ax25chat.log")
        if os.path.exists(pad) and os.path.getsize(pad) > systeem.LOG_MAX:
            os.replace(pad, pad + ".1")
        f = open(pad, "a", encoding="utf-8", buffering=1)
    except OSError:
        f = open(os.devnull, "w")
    sys.stdout = sys.stdout or f
    sys.stderr = sys.stderr or f
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


def zelftest(args, adres):
    """Voor GitHub Actions: start de server zonder venster, haal een paar pagina's op, schrijf de uitslag naar het
    bestand in AX25CHAT_ZELFTEST en stop. Zo is te zien of het Windows-programma compleet is."""
    uitslag = []
    import ax25chat_web as web
    klaar = threading.Event()
    web.KLAAR = lambda _: klaar.set()
    threading.Thread(target=web.main, args=(args,), daemon=True).start()
    klaar.wait(60)
    for pad, moet in (("status.json", "roepnaam"), ("radio", "Zoek mijn set"), ("leaflet/leaflet.js", "Leaflet"),
                      ("kaart", "kaart")):
        try:
            with urllib.request.urlopen(adres + pad, timeout=20) as r:
                tekst = r.read().decode("utf-8", errors="replace")
            uitslag.append(f"{'ok  ' if moet in tekst else 'FOUT'} /{pad}")
        except Exception as fout:
            uitslag.append(f"FOUT /{pad}: {fout}")
    import ax25chat_radio as radio
    for naam_, prog in (("direwolf", radio.DIREWOLF), ("rigctld", radio.RIGCTLD), ("rigctl", radio.rig.RIGCTL)):
        uitslag.append(f"{'ok  ' if os.path.isfile(prog) else 'FOUT'} {naam_}: {prog}")
    try:
        import importlib
        importlib.import_module("webview")
        uitslag.append("ok   pywebview")
    except Exception as fout:
        uitslag.append(f"FOUT pywebview: {fout}")
    with open(os.environ["AX25CHAT_ZELFTEST"], "w", encoding="utf-8") as f:
        f.write("\n".join(uitslag) + "\n")
    import ax25chat_systeem as systeem
    systeem.stop_diensten()
    return 1 if any(x.startswith("FOUT") for x in uitslag) else 0


def main():
    uitvoer_naar_logboek()
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
    if os.environ.get("AX25CHAT_ZELFTEST"):
        return zelftest(args, adres)
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
