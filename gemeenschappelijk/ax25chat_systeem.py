"""
ax25chat_systeem.py - alles wat per computer anders is, op één plek.

AX25Chat draait nu op een Raspberry Pi en later ook op een gewone Linux- of Windows-PC. De rest van
de code vraagt hier hoe je een dienst (her)start, het logboek van Direwolf leest, de geluidsniveaus
zet, even opneemt of een seriële poort opent. Zo hoeft alleen dit bestand te weten op welke computer
het draait.

    SOORT = "pi"   Raspberry Pi: diensten via systemd (sudo systemctl), logboek via journalctl,
                   geluid via amixer/arecord, hotspot en Bijwerken via thuis-wifi.
    SOORT = "pc"   gewone PC (komt in een volgende stap): het programma start Direwolf en rigctld
                   zelf, geen hotspot en geen Pi uit/herstart.

De soort komt uit AX25CHAT_SOORT; zonder die variabele is het "pi" op Linux en "pc" op Windows.
Alleen standaard-Python.
"""

import os
import subprocess
import sys

SOORT = (os.environ.get("AX25CHAT_SOORT") or ("pc" if sys.platform == "win32" else "pi")).lower()
IS_PI = SOORT == "pi"

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
        return False, "nog niet beschikbaar op deze computer"
    try:
        r = subprocess.run([SUDO, "-n", SYSTEMCTL, actie, naam], capture_output=True, text=True, timeout=30)
        return (True, "") if r.returncode == 0 else (False, (r.stderr or r.stdout).strip()[:200])
    except Exception as fout:
        return False, str(fout)


def dienst_status(naam):
    """'active', 'inactive', 'failed' ... of 'onbekend'."""
    if not IS_PI:
        return "onbekend"
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
        return ""
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
