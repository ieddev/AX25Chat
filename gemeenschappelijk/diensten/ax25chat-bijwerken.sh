#!/bin/bash
# AX25Chat bijwerken op de achtergrond (knop op het tabblad Status, dienst ax25chat-bijwerken).
# Draait als root (geïnstalleerd in /usr/local/lib/ax25chat, niet door de gebruiker te wijzigen) en
# start de gewone installatie als de AX25Chat-gebruiker. Omdat sudo bij die gebruiker een wachtwoord
# kan vragen, krijgt hij alleen zolang het bijwerken duurt sudo zonder wachtwoord; dat wordt daarna
# weggehaald (en bij een stroomstoring tijdens het bijwerken bij de volgende start, via tmpfiles.d).
# Altijd de code van GitHub (ieddev/AX25Chat), nooit wat er lokaal in de bronmap is veranderd.
# Stond de hotspot tijdelijk uit (thuis-wifi), dan gaat hij na afloop over 1 minuut weer aan.
U="$1"; MAP="$2"
LOG=/var/log/ax25chat-bijwerken.log
SUD=/etc/sudoers.d/ax25chat-bijwerken-tijdelijk
REPO=https://github.com/ieddev/AX25Chat
[ "$(id -u)" = 0 ] || { echo "Moet als root draaien."; exit 1; }
THUIS="$(getent passwd "$U" | cut -d: -f6)"
[ -n "$U" ] && [ -d "$THUIS" ] || { echo "Onbekende gebruiker: $U"; exit 1; }
BRON="$THUIS/ax25chat-bron"
trap 'rm -f "$SUD" "$SUD.tmp"' EXIT

als() { runuser -u "$U" -- env HOME="$THUIS" USER="$U" LOGNAME="$U" \
          PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "$@"; }

hotspot_straks() {
  if [ -f /run/ax25chat-thuiswifi ]; then
    echo "-- De hotspot gaat over 1 minuut weer aan. Verbind je telefoon daarna weer met de wifi van de Pi."
    bash /usr/local/lib/ax25chat/ax25chat-wifi.sh hotspot_later
  fi
}

{
  echo "== START $(date '+%Y-%m-%d %H:%M:%S') (via de webpagina)"
  echo "$U ALL=(ALL) NOPASSWD: ALL" > "$SUD.tmp"; chmod 0440 "$SUD.tmp"
  if ! visudo -cf "$SUD.tmp" >/dev/null; then echo "FOUT: tijdelijke sudo-regel ongeldig."; echo "== EINDE 2"; exit 0; fi
  mv "$SUD.tmp" "$SUD"
  if [ ! -d "$BRON/.git" ]; then
    rm -rf "$BRON"
    als git clone -q "$REPO" "$BRON" || { echo "FOUT: ophalen van GitHub mislukt (internet?)."; echo "== EINDE 3"; exit 0; }
  fi
  als git -C "$BRON" remote set-url origin "$REPO"
  if ! { als git -C "$BRON" fetch -q origin main && als git -C "$BRON" reset -q --hard origin/main; }; then
    echo "FOUT: ophalen van GitHub mislukt (internet?)."; echo "== EINDE 3"; exit 0
  fi
  echo "   versie: $(als git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M')"
  ( cd "$THUIS" && als env AX25CHAT_UIT_BRON=1 bash "$BRON/installeer.sh" </dev/null )
  RC=$?
  [ "$RC" = 0 ] && hotspot_straks
  echo "== EINDE $RC"
} >"$LOG" 2>&1
chmod 0644 "$LOG"
exit 0
