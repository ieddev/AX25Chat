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
import socket
import sys
import threading
import time
import urllib.request

os.environ.setdefault("AX25CHAT_SOORT", "pc")
HIER = os.path.dirname(os.path.abspath(__file__))
for deel in ("chat", "gemeenschappelijk"):
    sys.path.insert(0, os.path.join(HIER, "..", deel))

PICTOGRAM = os.path.join(HIER, "ax25chat.png")


LOGBOEK = ""                                       # pad van logboek/ax25chat.log (Windows-programma)


def uitvoer_naar_logboek():
    """Windows-programma zonder consolevenster: sys.stdout/stderr zijn er niet. Schrijf dan naar logboek/ax25chat.log
    in de map met instellingen, zodat er bij problemen iets na te lezen is. Ook een harde crash (bijvoorbeeld in
    WebView2) komt erin, via faulthandler."""
    global LOGBOEK
    if sys.stdout is not None and sys.stderr is not None:
        return
    import ax25chat_systeem as systeem
    try:
        os.makedirs(systeem.LOGMAP, exist_ok=True)
        pad = os.path.join(systeem.LOGMAP, "ax25chat.log")
        if os.path.exists(pad) and os.path.getsize(pad) > systeem.LOG_MAX:
            os.replace(pad, pad + ".1")
        f = open(pad, "a", encoding="utf-8", buffering=1)
        LOGBOEK = pad
    except OSError:
        f = open(os.devnull, "w")
    sys.stdout = sys.stdout or f
    sys.stderr = sys.stderr or f
    try:
        import faulthandler
        faulthandler.enable(file=f)
    except Exception:
        pass


def meld(tekst):
    """Regel in het logboek met de tijd ervoor, zodat te zien is hoe ver het opstarten kwam."""
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {tekst}", flush=True)


def beheerder():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def toon_fout(tekst):
    """Melding in beeld als AX25Chat niet kan starten (op Windows is er geen console waar het anders staat)."""
    meld("FOUT: " + tekst)
    if LOGBOEK:
        tekst += f"\n\nMeer staat in het logboek:\n{LOGBOEK}"
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, tekst, TITEL, 0x10)
    except Exception:
        pass


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


def poort_vrij(poort):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", poort))
            return True
        except OSError:
            return False


def vrije_poort():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def kies_poort(args):
    """(poort, args). Is 8080 al bezet door een ander programma (en niet door AX25Chat), dan neemt het venster een
    andere vrije poort; het venster maakt het niet uit welke. Bij --poort of --thuisnetwerk blijft de poort vast,
    want de telefoon of app rekent erop."""
    poort = poort_uit(args)
    if draait_al(poort) or poort_vrij(poort) or "--poort" in args or "--thuisnetwerk" in args:
        return poort, args
    nieuw = vrije_poort()
    meld(f"Poort {poort} is bezet door een ander programma; AX25Chat gebruikt nu poort {nieuw}.")
    return nieuw, [*args, "--poort", str(nieuw)]


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


def pakketversie(naam):
    try:
        from importlib.metadata import version
        return version(naam)
    except Exception:
        return "?"


def lees_versie():
    import ax25chat_systeem as systeem
    for map_ in (systeem.CODE, getattr(sys, "_MEIPASS", ""), HIER):
        try:
            with open(os.path.join(map_, "versie.txt"), encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return "onbekend"


def start_opties(webview):
    """Opties voor webview.start. De gegevens van het venster (WebView2/WebKit) komen in de map met instellingen,
    waar de gebruiker altijd mag schrijven, en niet naast het programma. icon= alleen als deze pywebview dat kent."""
    import inspect
    import ax25chat_systeem as systeem
    kent = inspect.signature(webview.start).parameters
    opties = {}
    if "storage_path" in kent:
        opties["storage_path"] = os.path.join(systeem.MAP, "webview")
    if "icon" in kent:
        opties["icon"] = PICTOGRAM
    return opties


def venstertest(venster):
    """Voor GitHub Actions (AX25CHAT_VENSTERTEST=<bestand>): opent het echte venster, wacht tot de pagina geladen is,
    schrijft 'ok venster' en sluit. Lukt dat niet binnen 90 seconden, dan 'FOUT venster' en stoppen."""
    uit = os.environ["AX25CHAT_VENSTERTEST"]

    def schrijf(tekst):
        with open(uit, "w", encoding="utf-8") as f:
            f.write(tekst + "\n")

    def geladen():
        try:
            titel = venster.evaluate_js("document.title")
        except Exception as fout:
            titel = f"? ({fout})"
        meld(f"Venstertest: pagina geladen, titel {titel!r}")
        schrijf(f"ok   venster: {titel}")
        threading.Timer(2, venster.destroy).start()

    def te_laat():
        schrijf("FOUT venster: na 90 seconden geen pagina")
        meld("Venstertest: te laat")
        os._exit(1)

    venster.events.loaded += geladen
    t = threading.Timer(90, te_laat)
    t.daemon = True
    t.start()


def main():
    uitvoer_naar_logboek()
    args = sys.argv[1:]
    meld(f"AX25Chat start (versie {lees_versie()}, Python {sys.version.split()[0]}"
         f"{', beheerder' if beheerder() else ''}) {' '.join(args)}")
    if "--wachtwoord" in args or "-h" in args or "--help" in args:
        import ax25chat_web as web
        return web.main(args)
    try:
        import webview
    except Exception as fout:
        meld(f"pywebview is niet te laden ({fout}): AX25Chat opent in de browser.")
        import ax25chat_pc
        return ax25chat_pc.main()

    if os.environ.get("AX25CHAT_ZELFTEST"):
        poort = poort_uit(args)
        return zelftest(args, f"http://localhost:{poort}/")
    poort, args = kies_poort(args)
    adres = f"http://localhost:{poort}/"
    draad = None
    if draait_al(poort):
        meld(f"AX25Chat draait al op poort {poort}: alleen een venster erbij.")
    else:
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
        if not klaar.wait(60):
            meld("Let op: de webserver is na 60 seconden nog niet klaar; het venster opent toch.")
        if fout:
            toon_fout("AX25Chat starten lukte niet: " + " ".join(fout))
            return 1
        meld(f"Webserver klaar op {adres}")
    try:
        venster = webview.create_window(TITEL, adres, width=1000, height=820, min_size=(360, 480), text_select=True)
        if os.environ.get("AX25CHAT_VENSTERTEST"):
            venstertest(venster)
        else:
            venster.events.loaded += lambda: meld("Venster geladen.")
        meld(f"Venster openen (pywebview {pakketversie('pywebview')})")
        webview.start(**start_opties(webview))   # blijft hier tot het venster dicht is
        meld("Venster gesloten.")
    except Exception as fout:                    # geen venster mogelijk (bijv. WebKit/WebView2 ontbreekt): browser
        import traceback
        traceback.print_exc()
        meld(f"Eigen venster lukte niet ({fout}); AX25Chat opent in de browser: {adres}")
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
