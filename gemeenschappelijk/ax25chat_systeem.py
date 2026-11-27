"""
ax25chat_systeem.py - alles wat per computer anders is, op één plek.

AX25Chat draait nu op een Raspberry Pi en later ook op een gewone Linux- of Windows-PC. De rest van
de code vraagt hier hoe je een dienst (her)start, het logboek van Direwolf leest, de geluidsniveaus
zet, even opneemt of een seriële poort opent. Zo hoeft alleen dit bestand te weten op welke computer
het draait.

    SOORT = "pi"   Raspberry Pi: diensten via systemd (sudo systemctl), logboek via journalctl,
                   geluid via amixer/arecord, hotspot en Bijwerken via thuis-wifi.
    SOORT = "pc"   gewone PC: het programma start Direwolf en rigctld zelf als kindproces, houdt zelf
                   een logboek bij (map logboek/), geen hotspot en geen Pi uit/herstart.

De soort komt uit AX25CHAT_SOORT; zonder die variabele is het "pi" op Linux en "pc" op Windows.
Alleen standaard-Python.
"""

import os
import subprocess
import sys
import threading
import time

SOORT = (os.environ.get("AX25CHAT_SOORT") or ("pc" if sys.platform == "win32" else "pi")).lower()
IS_PI = SOORT == "pi"
CODE = os.path.dirname(os.path.abspath(__file__))        # waar de programma's staan


def _datamap():
    """Map voor instellingen en gegevens. Pi: naast de programma's (~/ax25chat). PC: een eigen map per gebruiker."""
    if os.environ.get("AX25CHAT_MAP"):
        return os.environ["AX25CHAT_MAP"]
    if IS_PI:
        return CODE
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "AX25Chat")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "ax25chat")


MAP = _datamap()
if not IS_PI:
    os.makedirs(MAP, exist_ok=True)
LOGMAP = os.path.join(MAP, "logboek")
LOG_MAX = 2_000_000                     # bytes per logboek; daarna wordt het oude .1

SUDO = os.environ.get("AX25CHAT_SUDO", "sudo")
SYSTEMCTL = os.environ.get("AX25CHAT_SYSTEMCTL", "systemctl")
JOURNALCTL = os.environ.get("AX25CHAT_JOURNALCTL", "journalctl")
AMIXER = os.environ.get("AX25CHAT_AMIXER", "amixer")
ARECORD = os.environ.get("AX25CHAT_ARECORD", "arecord")


def uit(cmd, timeout=5):
    """Uitvoer van een opdracht als tekst, of "" als het niet lukt."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Wat kan deze computer (de webpagina laat de rest weg)
# ---------------------------------------------------------------------------

def kan(wat):
    """'hotspot', 'bijwerken_wifi', 'uitzetten' en 'mixer' alleen op de Pi (voorlopig)."""
    if wat in ("hotspot", "bijwerken_wifi", "uitzetten"):
        return IS_PI
    if wat == "mixer":
        return sys.platform != "win32"
    return True


# ---------------------------------------------------------------------------
# Diensten: Direwolf, rigctld, webserver
# ---------------------------------------------------------------------------

def dienst(actie, naam):
    """restart/stop/start van een eigen dienst. Geeft (ok, fout)."""
    if not IS_PI:
        return _pc_dienst(actie, naam)
    try:
        r = subprocess.run([SUDO, "-n", SYSTEMCTL, actie, naam], capture_output=True, text=True, timeout=30)
        return (True, "") if r.returncode == 0 else (False, (r.stderr or r.stdout).strip()[:200])
    except Exception as fout:
        return False, str(fout)


def dienst_status(naam):
    """'active', 'inactive', 'failed' ... of 'onbekend'."""
    if not IS_PI:
        return _pc_status(naam)
    return uit([SYSTEMCTL, "is-active", naam]).strip() or "onbekend"


def pi_uitzetten(actie):
    """actie 'uit' of 'herstart'. Alleen op de Pi."""
    if not IS_PI:
        return False
    subprocess.run([SUDO, "-n", SYSTEMCTL, "poweroff" if actie == "uit" else "reboot"],
                   capture_output=True, timeout=15)
    return True


# ---------------------------------------------------------------------------
# Logboek van een dienst
# ---------------------------------------------------------------------------

def logboek(naam, regels=None, sinds=None, uren=None, met_tijd=False, timeout=10):
    """Logregels van een dienst als tekst. regels = laatste n; sinds = 'JJJJ-MM-DD uu:mm:ss'; uren = laatste n uur.
    met_tijd: elke regel begint met de tijd (ISO), anders alleen de tekst."""
    if not IS_PI:
        return _pc_logboek(naam, regels, sinds, uren, met_tijd)
    cmd = [JOURNALCTL, "-u", naam, "--no-pager", "-o", "short-iso" if met_tijd else "cat"]
    if regels:
        cmd += ["-n", str(int(regels))]
    if sinds:
        cmd += ["--since", sinds]
    elif uren:
        cmd += ["--since", f"-{int(uren)}h"]
    return uit(cmd, timeout=timeout)


# ---------------------------------------------------------------------------
# Geluid: niveaus en even opnemen
# ---------------------------------------------------------------------------

def mixer_tekst(kaart):
    """'amixer scontents' van de geluidskaart (leeg als er geen mixer is)."""
    return uit([AMIXER, "-c", kaart, "scontents"]) if kan("mixer") else ""


def mixer_zet(kaart, regelaar, procent, extra=()):
    """Zet één regelaar op procent. Gooit een fout als het niet lukt."""
    subprocess.run([AMIXER, "-q", "-c", kaart, "sset", regelaar, f"{int(procent)}%", *extra],
                   check=True, capture_output=True, text=True, timeout=5)


def neem_op(kaart, seconden):
    """Neem seconden op (48 kHz, mono, 16 bit). Geeft (ruwe bytes, foutmelding)."""
    try:
        p = subprocess.run([ARECORD, "-q", "-D", f"plughw:CARD={kaart},DEV=0", "-f", "S16_LE", "-r", "48000",
                            "-c", "1", "-t", "raw", "-d", str(int(seconden))],
                           capture_output=True, timeout=seconden + 10)
        return p.stdout, p.stderr.decode(errors="replace").strip()
    except Exception as x:
        return b"", str(x)


# ---------------------------------------------------------------------------
# Seriële poort (GPS-muis), alleen lezen
# ---------------------------------------------------------------------------

def open_serieel(pad, baud=9600):
    """Open een seriële poort om te lezen, niet-blokkerend. Geeft een bestandsnummer (os.read/os.close)."""
    import termios                                     # bestaat niet op Windows
    fd = os.open(pad, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    snelheid = getattr(termios, f"B{baud}", termios.B9600)
    a[0] = termios.IGNPAR                              # iflag
    a[1] = 0                                           # oflag
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    a[3] = 0                                           # lflag: geen echo, niet regel voor regel
    a[4] = a[5] = snelheid
    termios.tcsetattr(fd, termios.TCSANOW, a)
    return fd


# ---------------------------------------------------------------------------
# PC: Direwolf en rigctld als kindproces (in plaats van systemd)
# ---------------------------------------------------------------------------
#
# Een dienst wordt aangemeld met een functie die de opdracht geeft (of None: niets te doen, bijv. rigctld
# zonder CAT) en eventueel een functie die vóór het starten draait (niveaus zetten, wachten op rigctld).
# Stopt het programma vanzelf, dan start het na 5 seconden opnieuw, net als Restart=always bij systemd.

_DIENSTEN = {}          # naam -> {"opdracht": f, "voor": f, "proc": Popen, "aan": bool, "lock": Lock}
OPNIEUW_NA = 5


def meld_dienst(naam, opdracht, voor=None):
    """Meld een dienst aan voor de PC. opdracht() -> [programma, argumenten] of None. voor() draait vlak voor het starten."""
    _DIENSTEN[naam] = {"opdracht": opdracht, "voor": voor, "proc": None, "aan": False, "nodig": True,
                       "lock": threading.Lock(), "fout": "", "gen": 0}


def start_diensten(namen=None):
    """Start de aangemelde diensten (in volgorde van aanmelden). Geeft [fouten]."""
    fouten = []
    for naam in (namen or list(_DIENSTEN)):
        ok, fout = _pc_dienst("start", naam)
        if not ok:
            fouten.append(f"{naam}: {fout}")
    return fouten


def stop_diensten():
    for naam in reversed(list(_DIENSTEN)):
        _pc_dienst("stop", naam)


def _logregel(naam, tekst):
    """Eén regel in logboek/<naam>.log, met de tijd ervoor zoals journalctl -o short-iso."""
    try:
        os.makedirs(LOGMAP, exist_ok=True)
        pad = os.path.join(LOGMAP, naam + ".log")
        if os.path.exists(pad) and os.path.getsize(pad) > LOG_MAX:
            os.replace(pad, pad + ".1")
        with open(pad, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {naam}: {tekst.rstrip()}\n")
    except OSError:
        pass


def _lees_uitvoer(naam, proc):
    with proc.stdout:
        for regel in iter(proc.stdout.readline, b""):
            _logregel(naam, regel.decode("utf-8", errors="replace"))


def _bewaak(naam, d, gen):
    """Draait zolang de dienst aan staat: start, wacht tot het programma stopt, start opnieuw.
    gen: na een stop of herstart hoort deze draad er niet meer bij en start hij niets meer."""
    def mag():
        return d["aan"] and d["gen"] == gen
    while mag():
        try:
            if d["voor"]:
                d["voor"]()
        except Exception as fout:
            _logregel(naam, f"[AX25Chat] voorbereiden mislukt: {fout}")
        with d["lock"]:
            if not mag():
                return
            cmd = d["opdracht"]()
            if not cmd:
                d["nodig"] = False
                return
            d["nodig"] = True
            try:
                p = subprocess.Popen(cmd, cwd=MAP, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                d["proc"], d["fout"] = p, ""
                _logregel(naam, "[AX25Chat] gestart: " + " ".join(cmd))
            except OSError as fout:
                d["fout"] = f"{cmd[0]} starten lukte niet: {fout}"
                _logregel(naam, "[AX25Chat] " + d["fout"])
                p = None
        if p:
            threading.Thread(target=_lees_uitvoer, args=(naam, p), daemon=True).start()
            code = p.wait()
            if mag():
                d["fout"] = f"gestopt met code {code}"
                _logregel(naam, f"[AX25Chat] {cmd[0]} gestopt (code {code}); opnieuw over {OPNIEUW_NA} s")
        eind = time.time() + OPNIEUW_NA
        while mag() and time.time() < eind:
            time.sleep(0.2)


def _pc_dienst(actie, naam):
    d = _DIENSTEN.get(naam)
    if not d:
        return False, "onbekende dienst"
    if actie not in ("start", "stop", "restart"):
        return False, "onbekende actie"
    with d["lock"]:
        if actie in ("stop", "restart"):
            d["aan"] = False
            d["gen"] += 1
            p, d["proc"] = d["proc"], None
        else:
            p = None
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)
    with d["lock"]:
        if actie in ("start", "restart") and not d["aan"]:
            d["aan"], d["fout"], d["nodig"] = True, "", True
            d["gen"] += 1
            threading.Thread(target=_bewaak, args=(naam, d, d["gen"]), daemon=True).start()
    return True, ""


def _pc_status(naam):
    d = _DIENSTEN.get(naam)
    if not d:
        return "active" if naam == "ax25chat-web" else "onbekend"
    if not d["aan"]:
        return "inactive"
    if not d["nodig"]:
        return "niet nodig"
    p = d["proc"]
    if p and p.poll() is None:
        return "active"
    return "failed" if d["fout"] else "activating"


def _pc_logboek(naam, regels=None, sinds=None, uren=None, met_tijd=False):
    pad = os.path.join(LOGMAP, naam + ".log")
    try:
        with open(pad, encoding="utf-8", errors="replace") as f:
            lijst = f.read().splitlines()
    except OSError:
        return ""
    grens = None
    if sinds:
        grens = sinds.replace(" ", "T")[:19]
    elif uren:
        grens = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - float(uren) * 3600))
    if grens:
        lijst = [x for x in lijst if x[:19] >= grens]
    if regels:
        lijst = lijst[-int(regels):]
    if not met_tijd:
        lijst = [x.split(": ", 1)[1] if ": " in x else x for x in lijst]
    return "\n".join(lijst) + ("\n" if lijst else "")
