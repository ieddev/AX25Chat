"""
ax25chat_locator.py - Maidenhead-locators (bijv. JO32CD) lezen, voor stations zonder APRS-positie op de kaart.

Veel nodes en BBS'en (bijv. een BPQ-node) sturen geen APRS-positie, maar noemen hun locator in hun baken.
Zo'n locator is een vak, geen punt: we tekenen het station op het midden van het vak, met een eigen symbool.

    JO       veld        20° x 10°
    JO32     vak         2° x 1°        (ca. 135 x 110 km in Nederland)
    JO32CD   subvak      5' x 2,5'      (ca. 6 x 5 km)
    JO32CD45 nog kleiner 30" x 15"      (ca. 600 x 460 m)

Herkennen in gewone tekst: een locator van 6 of 8 tekens altijd; een korte van 4 tekens (JO32) alleen
direct na LOC, LOCATOR, QTH of QRA, want losse combinaties als 'AB12' komen te vaak voor.
Alleen standaard-Python.
"""

import re

_LOC = re.compile(r"^[A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2})?)?$")
_LANG = re.compile(r"(?<![A-Za-z0-9])([A-Ra-r]{2}[0-9]{2}[A-Xa-x]{2}(?:[0-9]{2})?)(?![A-Za-z0-9])")
_KORT = re.compile(r"(?<![A-Za-z0-9])(?:LOC(?:ATOR)?|QTH|QRA)\s*[:=]?\s*([A-R]{2}[0-9]{2})(?![A-Za-z0-9])", re.I)


def schoon(loc):
    """'jo32cd' -> 'JO32CD'; ongeldig -> ''."""
    loc = str(loc or "").strip().upper().replace(" ", "")
    return loc if _LOC.match(loc) else ""


def vak(loc):
    """(zuid, west, noord, oost) van het locatorvak, of None."""
    loc = schoon(loc)
    if not loc:
        return None
    lon = (ord(loc[0]) - 65) * 20 - 180
    lat = (ord(loc[1]) - 65) * 10 - 90
    lon += int(loc[2]) * 2
    lat += int(loc[3])
    dlon, dlat = 2.0, 1.0
    if len(loc) >= 6:
        dlon, dlat = 5 / 60, 2.5 / 60
        lon += (ord(loc[4]) - 65) * dlon
        lat += (ord(loc[5]) - 65) * dlat
    if len(loc) == 8:
        dlon, dlat = dlon / 10, dlat / 10
        lon += int(loc[6]) * dlon
        lat += int(loc[7]) * dlat
    return (round(lat, 6), round(lon, 6), round(lat + dlat, 6), round(lon + dlon, 6))


def midden(loc):
    """(lat, lon) van het midden van het vak, of None."""
    v = vak(loc)
    return (round((v[0] + v[2]) / 2, 5), round((v[1] + v[3]) / 2, 5)) if v else None


def zoek(tekst):
    """De eerste locator in een stuk gewone tekst, of ''. Getekende letters (ASCII-art) zijn niet te lezen."""
    tekst = str(tekst or "")
    m = _LANG.search(tekst)
    if m:
        return schoon(m.group(1))
    m = _KORT.search(tekst)
    return schoon(m.group(1)) if m else ""


def info(loc):
    """Alles wat de kaart nodig heeft: {'locator', 'lat', 'lon', 'vak'} of None."""
    v = vak(loc)
    if not v:
        return None
    lat, lon = midden(loc)
    return {"locator": schoon(loc), "lat": lat, "lon": lon, "vak": list(v)}


_CALL = re.compile(r"^[A-Z0-9]{3,7}(-[0-9]{1,2})?$")
MAX_HANDMATIG = 100


def handmatig(station):
    """Zelf ingevulde locators uit station.json: {roepnaam: locator}."""
    uit = {}
    for call, loc in (station.get("locators") or {}).items() if isinstance(station.get("locators"), dict) else []:
        call, loc = str(call).upper(), schoon(loc)
        if _CALL.match(call) and loc:
            uit[call] = loc
    return uit


def zet_handmatig(station, call, loc):
    """Locator voor een roepnaam invullen (lege locator: weghalen). Past station aan; geeft een foutmelding of ''."""
    call = str(call or "").strip().upper().replace(" ", "")
    call = call[:-2] if call.endswith("-0") else call
    if not _CALL.match(call):
        return "Roepnaam: bijv. PD4R-12."
    lijst = handmatig(station)
    if str(loc or "").strip():
        loc = schoon(loc)
        if not loc:
            return "Locator: 4, 6 of 8 tekens, bijv. JO32CD (twee letters A-R, twee cijfers, twee letters A-X)."
        if call not in lijst and len(lijst) >= MAX_HANDMATIG:
            return f"Hoogstens {MAX_HANDMATIG} stations; haal er eerst een weg."
        lijst[call] = loc
    else:
        lijst.pop(call, None)
    station["locators"] = dict(sorted(lijst.items()))
    return ""

