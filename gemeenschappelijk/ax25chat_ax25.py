"""
ax25chat_ax25.py - KISS en AX.25 UI-frames, en de verbinding met Direwolf (KISS over TCP).

Overgenomen uit Noodnet (noodnet_proto.py), met een digipeaterpad erbij (bijv. WIDE1-1).
Het berichtformaat van de chat (APRS-berichten, CQ) komt in stap 2.

Alleen standaard-Python.
"""

import socket
import threading
import time

TOCALL = "APZAXC"         # AX.25-bestemming (APZ = experimenteel)
DIREWOLF = ("127.0.0.1", 8001)


# ---------------------------------------------------------------------------
# KISS
# ---------------------------------------------------------------------------

FEND, FESC, TFEND, TFESC = 0xC0, 0xDB, 0xDC, 0xDD


def kiss_encode(ax25_frame, port=0):
    out = bytearray([FEND, (port & 0x0F) << 4])
    for b in ax25_frame:
        if b == FEND:
            out += bytes([FESC, TFEND])
        elif b == FESC:
            out += bytes([FESC, TFESC])
        else:
            out.append(b)
    out.append(FEND)
    return bytes(out)


class KissDecoder:
    """Haalt complete AX.25-frames uit een KISS-bytestroom."""

    def __init__(self):
        self.buf = bytearray()
        self.in_frame = False
        self.escape = False

    def feed(self, data):
        frames = []
        for b in data:
            if b == FEND:
                if self.in_frame and len(self.buf) > 1:
                    cmd = self.buf[0]
                    if cmd & 0x0F == 0x00:          # alleen dataframes
                        frames.append(bytes(self.buf[1:]))
                self.buf = bytearray()
                self.in_frame = True
                self.escape = False
                continue
            if not self.in_frame:
                continue
            if self.escape:
                if b == TFEND:
                    self.buf.append(FEND)
                elif b == TFESC:
                    self.buf.append(FESC)
                self.escape = False
            elif b == FESC:
                self.escape = True
            else:
                self.buf.append(b)
        return frames


# ---------------------------------------------------------------------------
# AX.25 UI-frames
# ---------------------------------------------------------------------------

def _split_call(call):
    call = call.strip().upper()
    if "-" in call:
        base, ssid = call.split("-", 1)
        ssid = int(ssid)
    else:
        base, ssid = call, 0
    if not (1 <= len(base) <= 6) or not (0 <= ssid <= 15):
        raise ValueError(f"Ongeldige roepnaam: {call}")
    return base, ssid


def _encode_addr(call, last, command):
    base, ssid = _split_call(call)
    out = bytearray((ord(c) << 1) for c in base.ljust(6))
    b = 0x60 | (ssid << 1)
    if command:
        b |= 0x80
    if last:
        b |= 0x01
    out.append(b)
    return bytes(out)


def _decode_addr(raw):
    base = "".join(chr(b >> 1) for b in raw[:6]).strip()
    ssid = (raw[6] >> 1) & 0x0F
    return f"{base}-{ssid}" if ssid else base


def ax25_ui(src, dest, info, via=()):
    """Bouwt een AX.25 UI-frame, eventueel met een digipeaterpad (bijv. ["WIDE1-1"], maximaal 8)."""
    if isinstance(info, str):
        info = info.encode("utf-8")
    via = [v for v in via if v][:8]
    adres = _encode_addr(dest, last=False, command=True) + _encode_addr(src, last=not via, command=False)
    for i, v in enumerate(via):
        adres += _encode_addr(v, last=i == len(via) - 1, command=False)
    return adres + bytes([0x03, 0xF0]) + info


def ax25_parse(frame):
    """Geeft (bron, bestemming, info) terug, of None als het geen UI-frame is."""
    addrs = []
    i = 0
    while i + 7 <= len(frame):
        addrs.append(frame[i:i + 7])
        last = frame[i + 6] & 0x01
        i += 7
        if last:
            break
    else:
        return None
    if len(addrs) < 2 or i + 2 > len(frame):
        return None
    control, pid = frame[i], frame[i + 1]
    if control & 0xEF != 0x03 or pid != 0xF0:
        return None
    return _decode_addr(addrs[1]), _decode_addr(addrs[0]), frame[i + 2:]


# ---------------------------------------------------------------------------
# Verbinding met Direwolf (KISS over TCP)
# ---------------------------------------------------------------------------

class KissLink:
    """Houdt een KISS-TCP-verbinding met Direwolf open en maakt opnieuw
    verbinding als die wegvalt.

    on_frame(bron, bestemming, info_bytes) wordt aangeroepen voor elk
    ontvangen UI-frame.
    """

    def __init__(self, host, port, mycall, on_frame, log=print):
        self.host, self.port = host, port
        self.mycall = mycall
        self.on_frame = on_frame
        self.log = log
        self.sock = None
        self.lock = threading.Lock()
        self.running = True
        self.connected = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        warned = False
        while self.running:
            try:
                s = socket.create_connection((self.host, self.port), timeout=10)
                s.settimeout(None)
                with self.lock:
                    self.sock = s
                self.connected.set()
                warned = False
                self.log(f"[+] Direwolf: verbonden met {self.host}:{self.port}")
                dec = KissDecoder()
                while self.running:
                    data = s.recv(4096)
                    if not data:
                        raise ConnectionError("verbinding gesloten door Direwolf")
                    for frame in dec.feed(data):
                        parsed = ax25_parse(frame)
                        if parsed:
                            try:
                                self.on_frame(*parsed)
                            except Exception as e:
                                self.log(f"[-] Fout bij verwerken frame: {e}")
            except Exception as e:
                self.connected.clear()
                with self.lock:
                    if self.sock:
                        try:
                            self.sock.close()
                        except OSError:
                            pass
                    self.sock = None
                if self.running and not warned:
                    self.log(f"[!] Direwolf niet bereikbaar ({e}); blijf het elke 5 s proberen...")
                    warned = True
                time.sleep(5)

    def send_info(self, info, dest=TOCALL, via=()):
        """Zendt één UI-frame met deze info-tekst. Geeft True bij succes."""
        frame = kiss_encode(ax25_ui(self.mycall, dest, info, via))
        with self.lock:
            if not self.sock:
                return False
            try:
                self.sock.sendall(frame)
                return True
            except OSError as e:
                self.log(f"[-] Direwolf: zenden mislukt: {e}")
                return False

    def close(self):
        self.running = False
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
