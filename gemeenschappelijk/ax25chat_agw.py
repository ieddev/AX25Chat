"""
ax25chat_agw.py - verbinding met Direwolf via het AGW-protocol (AGWPE), voor connected mode (BBS'en).

Direwolf doet het eigenlijke AX.25-werk (SABM/UA, herhalen, volgnummers). Dit bestand praat alleen
het AGW-protocol: een kop van 36 bytes plus data.

    soort  richting  betekenis
    X      ->  <-    roepnaam aanmelden (antwoord: 1 byte, 1 = gelukt)
    C / v  ->        verbinden (v: via digipeaters)
    C      <-        verbonden ("*** CONNECTED To/With Station ...")
    D      ->  <-    tekst in de verbinding
    d      ->  <-    verbreken / verbroken ("*** DISCONNECTED ...")
    Y      ->  <-    hoeveel frames nog niet bevestigd zijn

Alleen standaard-Python.
"""

import socket
import struct
import threading
import time

DIREWOLF_AGW = ("127.0.0.1", 8000)
KOP = struct.Struct("<B3xBxBx10s10sII")      # poort, soort, pid, van, aan, lengte, gereserveerd


def pakket(soort, van="", aan="", data=b"", pid=0, poort=0):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return KOP.pack(poort, ord(soort), pid, van.upper().encode("ascii"), aan.upper().encode("ascii"),
                    len(data), 0) + data


def _call(raw):
    return raw.split(b"\0", 1)[0].decode("ascii", "replace").strip().upper()


class AgwLink:
    """Houdt een TCP-verbinding met de AGW-poort van Direwolf open en maakt opnieuw verbinding als die wegvalt.

    bij_pakket(soort, van, aan, data) wordt aangeroepen voor elk binnenkomend pakket (soort is een letter).
    bij_verbinding(bool) bij het openen (True) en wegvallen (False) van de TCP-verbinding met Direwolf.
    """

    def __init__(self, bij_pakket, bij_verbinding=None, adres=DIREWOLF_AGW, log=print):
        self.adres = adres
        self.bij_pakket = bij_pakket
        self.bij_verbinding = bij_verbinding or (lambda ok: None)
        self.log = log
        self.sock = None
        self.lock = threading.Lock()
        self.running = True
        self.verbonden = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        gewaarschuwd = False
        while self.running:
            try:
                s = socket.create_connection(self.adres, timeout=10)
                s.settimeout(None)
                with self.lock:
                    self.sock = s
                self.verbonden.set()
                gewaarschuwd = False
                self.log(f"[+] Direwolf AGW: verbonden met {self.adres[0]}:{self.adres[1]}")
                self.bij_verbinding(True)
                buf = b""
                while self.running:
                    data = s.recv(4096)
                    if not data:
                        raise ConnectionError("verbinding gesloten door Direwolf")
                    buf += data
                    while len(buf) >= KOP.size:
                        _, soort, _, van, aan, lengte, _ = KOP.unpack_from(buf)
                        if len(buf) < KOP.size + lengte:
                            break
                        inhoud, buf = buf[KOP.size:KOP.size + lengte], buf[KOP.size + lengte:]
                        try:
                            self.bij_pakket(chr(soort), _call(van), _call(aan), inhoud)
                        except Exception as e:
                            self.log(f"[-] AGW: fout bij verwerken: {e}")
            except Exception as e:
                was = self.verbonden.is_set()
                self.verbonden.clear()
                with self.lock:
                    if self.sock:
                        try:
                            self.sock.close()
                        except OSError:
                            pass
                    self.sock = None
                if was:
                    self.bij_verbinding(False)
                if self.running and not gewaarschuwd:
                    self.log(f"[!] Direwolf AGW niet bereikbaar ({e}); blijf het elke 3 s proberen...")
                    gewaarschuwd = True
                time.sleep(3)

    def stuur(self, soort, van="", aan="", data=b"", pid=0):
        with self.lock:
            if not self.sock:
                return False
            try:
                self.sock.sendall(pakket(soort, van, aan, data, pid))
                return True
            except OSError as e:
                self.log(f"[-] AGW: zenden mislukt: {e}")
                return False

    def aanmelden(self, mijn):
        return self.stuur("X", mijn)

    def afmelden(self, mijn):
        return self.stuur("x", mijn)

    def verbind(self, mijn, naar, via=()):
        via = [v.upper() for v in via if v][:7]
        if not via:
            return self.stuur("C", mijn, naar, pid=0xF0)
        data = bytes([len(via)]) + b"".join(v.encode("ascii").ljust(10, b"\0") for v in via)
        return self.stuur("v", mijn, naar, data, pid=0xF0)

    def tekst(self, mijn, naar, data):
        return self.stuur("D", mijn, naar, data, pid=0xF0)

    def verbreek(self, mijn, naar):
        return self.stuur("d", mijn, naar)

    def close(self):
        self.running = False
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
