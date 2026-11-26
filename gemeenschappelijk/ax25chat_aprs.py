"""
ax25chat_aprs.py - posities uit gehoorde APRS-frames halen, voor de kaart.

Drie vormen komen in de lucht voor, en alle drie worden gelezen:

    !5212.34N/00612.34E>088/036 commentaar      gewone positie (ook = / @, met of zonder tijd)
    =/5L!!<*e7>7P[ commentaar                   gecomprimeerd (o.a. trackers en sommige APRSdroid-instellingen)
    `c_Vm6hk/`"49}...  (bestemming T2SP0W)      Mic-E: Kenwood, Yaesu en veel trackers; de breedte staat in de bestemming

Objecten (;) en items ()) slaan we voorlopig over. Alleen standaard-Python.
"""

import re

KNOOP_KMH = 1.852
_ONGECOMP = re.compile(r"^(\d{2})([\d ]{2})\.([\d ]{2})([NS])(.)(\d{3})([\d ]{2})\.([\d ]{2})([EW])(.)")
_TABEL = re.compile(r"[/\\A-Za-j0-9]")
_KOERS = re.compile(r"^(\d{3})/(\d{3})")


def _b91(t):
    v = 0
    for c in t:
        n = ord(c) - 33
        if not 0 <= n <= 90:
            raise ValueError
        v = v * 91 + n
    return v


def _ongecomprimeerd(t):
    m = _ONGECOMP.match(t)
    if not m:
        return None
    lat = int(m.group(1)) + float(m.group(2).replace(" ", "0") + "." + m.group(3).replace(" ", "0")) / 60
    lon = int(m.group(6)) + float(m.group(7).replace(" ", "0") + "." + m.group(8).replace(" ", "0")) / 60
    if m.group(4) == "S":
        lat = -lat
    if m.group(9) == "W":
        lon = -lon
    rest = t[m.end():]
    p = {"lat": lat, "lon": lon, "symbool": m.group(5) + m.group(10), "koers": None, "kmh": None}
    k = _KOERS.match(rest)
    if k and p["symbool"][1] != "_":                    # bij weerstations is dit wind, geen koers
        p["koers"], p["kmh"] = int(k.group(1)) % 360, round(int(k.group(2)) * KNOOP_KMH)
        rest = rest[7:]
    p["commentaar"] = rest
    return p


def _gecomprimeerd(t):
    if len(t) < 13 or not _TABEL.match(t[0]):
        return None
    try:
        lat = 90 - _b91(t[1:5]) / 380926
        lon = -180 + _b91(t[5:9]) / 190463
    except ValueError:
        return None
    p = {"lat": lat, "lon": lon, "symbool": t[0] + t[9], "koers": None, "kmh": None, "commentaar": t[13:]}
    c, s = ord(t[10]) - 33, ord(t[11]) - 33
    if t[10] != " " and 0 <= c <= 89 and 0 <= s <= 90 and not (ord(t[12]) - 33) & 0x18 == 0x10:
        p["koers"], p["kmh"] = (c * 4) % 360, round((1.08 ** s - 1) * KNOOP_KMH)
    return p


def _mic_e(info, bestemming):
    d = bestemming.split("-")[0].upper()
    if len(d) != 6 or len(info) < 9:
        return None
    cijfers = []
    for c in d:
        if c.isdigit():
            cijfers.append(int(c))
        elif "A" <= c <= "J":
            cijfers.append(ord(c) - ord("A"))
        elif "P" <= c <= "Y":
            cijfers.append(ord(c) - ord("P"))
        elif c in "KLZ":
            cijfers.append(0)                            # positie-ambiguïteit: tellen als 0
        else:
            return None
    lat = cijfers[0] * 10 + cijfers[1] + (cijfers[2] * 10 + cijfers[3] + (cijfers[4] * 10 + cijfers[5]) / 100) / 60
    noord = "P" <= d[3] <= "Z"
    plus100 = "P" <= d[4] <= "Z"
    west = "P" <= d[5] <= "Z"
    b = [ord(c) - 28 for c in info[1:7]]
    graden = b[0] + (100 if plus100 else 0)
    if 180 <= graden <= 189:
        graden -= 80
    elif 190 <= graden <= 199:
        graden -= 190
    minuten = b[1] - 60 if b[1] >= 60 else b[1]
    lon = graden + (minuten + b[2] / 100) / 60
    if not (0 <= lat <= 90 and 0 <= lon <= 180 and 0 <= minuten < 60):
        return None
    knopen = b[3] * 10 + b[4] // 10
    if knopen >= 800:
        knopen -= 800
    koers = (b[4] % 10) * 100 + b[5]
    if koers >= 400:
        koers -= 400
    commentaar = info[9:]
    if commentaar[:1] in (">", "]", "`", "'"):          # soort set (Kenwood/Yaesu), niet interessant
        commentaar = commentaar[1:]
    return {"lat": lat if noord else -lat, "lon": -lon if west else lon, "symbool": info[8] + info[7],
            "koers": koers % 360 if knopen else None, "kmh": round(knopen * KNOOP_KMH) if knopen else None,
            "commentaar": commentaar}


def lees_positie(info, bestemming=""):
    """Positie uit het info-veld van een APRS-frame: {'lat', 'lon', 'symbool', 'koers', 'kmh', 'commentaar'} of None.
    symbool is twee tekens: tabel ('/' of '\\') en code (bijv. '>' auto, '-' huis)."""
    if isinstance(info, (bytes, bytearray)):
        info = info.decode("latin-1")
    if not info:
        return None
    try:
        soort = info[0]
        if soort in "`'\x1c\x1d":
            p = _mic_e(info, bestemming)
        elif soort in "!=/@":
            t = info[8:] if soort in "/@" else info[1:]       # / en @: eerst een tijd van 7 tekens
            p = _ongecomprimeerd(t) if t[:1].isdigit() else _gecomprimeerd(t)
        else:
            return None
    except (IndexError, ValueError):
        return None
    if not p or not (-90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180) or (p["lat"] == 0 and p["lon"] == 0):
        return None
    p["lat"], p["lon"] = round(p["lat"], 5), round(p["lon"], 5)
    p["commentaar"] = "".join(c for c in p["commentaar"] if c.isprintable()).strip()[:80]
    return p
