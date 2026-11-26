#!/bin/bash
# =============================================================================
#  AX25Chat - installatie en bijwerken op een Raspberry Pi (Zero 2W of 4)
#
#  Op een verse Pi met Raspberry Pi OS Lite (64-bit), internet via wifi of kabel:
#
#     bash <(curl -sL https://raw.githubusercontent.com/ieddev/AX25Chat/main/installeer.sh)
#
#  Nog een keer draaien = bijwerken (instellingen blijven bewaard).
#  Opnieuw alle vragen beantwoorden:   ... installeer.sh --opnieuw
#
#  De opzet komt uit Noodnet (github.com/ieddev/noodnet).
# =============================================================================
set -e
REPO="https://github.com/ieddev/AX25Chat"
RAW="https://raw.githubusercontent.com/ieddev/AX25Chat/main"
BRON="$HOME/ax25chat-bron"
DOEL="$HOME/ax25chat"
GEBRUIKER="$(id -un)"

rood()  { printf '\033[1;31m%s\033[0m\n' "$*"; }
groen() { printf '\033[1;32m%s\033[0m\n' "$*"; }
stap()  { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }

# ---------------------------------------------------------------------------
# 0. Bootstrap: haal de nieuwste versie van GitHub en start die
# ---------------------------------------------------------------------------
if [ "${AX25CHAT_UIT_BRON:-0}" != "1" ]; then
  [ "$(id -u)" = "0" ] && { rood "Start dit NIET met sudo, maar als gewone gebruiker."; exit 1; }
  stap "AX25Chat ophalen van GitHub"
  if ! command -v git >/dev/null 2>&1; then sudo apt-get update -qq && sudo apt-get install -y -qq git; fi
  if [ -d "$BRON/.git" ]; then
    git -C "$BRON" fetch -q origin main && git -C "$BRON" reset -q --hard origin/main
  else
    git clone -q "$REPO" "$BRON"
  fi
  echo "   versie: $(git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M')"
  AX25CHAT_UIT_BRON=1 exec bash "$BRON/installeer.sh" "$@"
fi

# ---------------------------------------------------------------------------
# 1. Vragen (alleen bij de eerste installatie of met --opnieuw)
# ---------------------------------------------------------------------------
OPNIEUW=0; [ "$1" = "--opnieuw" ] && OPNIEUW=1
mkdir -p "$DOEL"
NIEUW=0
if [ ! -f "$DOEL/station.json" ] || [ "$OPNIEUW" = "1" ]; then
  NIEUW=1
  clear || true
  cat <<'TXT'
 ===========================================================
   AX25Chat - installatie
 ===========================================================
TXT
  while true; do
    read -r -p "   Je roepnaam met SSID (bijv. PD3PAM-7): " RN
    RN="$(echo "$RN" | tr '[:lower:]' '[:upper:]' | tr -d ' ')"
    [[ "$RN" =~ ^[A-Z0-9]{3,6}(-([0-9]|1[0-5]))?$ ]] && break
    rood "   Gebruik je roepnaam, eventueel met streepje-SSID, bijvoorbeeld PD3PAM-7"
  done
  echo
  echo "   De Pi maakt een eigen wifi-hotspot 'AX25Chat-$RN'."
  while true; do
    read -r -p "   Wachtwoord voor die hotspot (min. 8 tekens, Enter = zelf laten kiezen): " HPW
    [ -z "$HPW" ] && HPW="$(tr -dc 'a-hjkmnp-z2-9' </dev/urandom | head -c 10)"
    [ ${#HPW} -ge 8 ] && break
    rood "   Minstens 8 tekens."
  done
  echo "   Hotspot-wachtwoord: $HPW   (schrijf dit op; staat ook op het tabblad Status)"
  python3 - "$DOEL/station.json" "$RN" <<'PY'
import json, os, sys
pad, rn = sys.argv[1], sys.argv[2]
s = {}
if os.path.exists(pad):
    s = json.load(open(pad, encoding="utf-8"))
s.update(roepnaam=rn)
s.setdefault("frequentie", 144900000)
json.dump(s, open(pad, "w", encoding="utf-8"), indent=2)
PY
fi

# ---------------------------------------------------------------------------
# 2. Pakketten
# ---------------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
APT_OPT=(-y -qq -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)
stap "Raspberry Pi OS bijwerken (de eerste keer kan dit 10-20 minuten duren)"
sudo apt-get update -qq
sudo -E apt-get full-upgrade "${APT_OPT[@]}"
sudo apt-get autoremove -y -qq || true

stap "Pakketten installeren"
sudo -E apt-get install "${APT_OPT[@]}" git python3 direwolf alsa-utils iw curl hostapd dnsmasq-base rfkill libhamlib-utils
sudo usermod -aG dialout,audio,plugdev,systemd-journal "$GEBRUIKER" || true
# De standaard-dienst van het pakket direwolf niet gebruiken (AX25Chat heeft een eigen)
sudo systemctl disable -q --now direwolf 2>/dev/null || true

# Logboek bewaren tussen herstarts (max. 64 MB): journalctl -b -1
if [ ! -f /etc/systemd/journald.conf.d/ax25chat.conf ]; then
  sudo install -d -m 0755 /etc/systemd/journald.conf.d
  printf '[Journal]\nStorage=persistent\nSystemMaxUse=64M\n' | sudo tee /etc/systemd/journald.conf.d/ax25chat.conf >/dev/null
  sudo install -d -m 2755 -g systemd-journal /var/log/journal
  sudo systemctl restart systemd-journald || true
fi

# ---------------------------------------------------------------------------
# 3. Programma's kopiëren (instellingen en gegevens blijven staan)
# ---------------------------------------------------------------------------
stap "AX25Chat-programma's naar $DOEL"
cp "$BRON"/gemeenschappelijk/*.py "$BRON"/gemeenschappelijk/*.sh "$DOEL"/
cp "$BRON"/chat/*.py "$DOEL"/
mkdir -p "$DOEL/leaflet" && cp "$BRON"/gemeenschappelijk/leaflet/* "$DOEL/leaflet/"   # kaart (tabblad Kaart)
chmod +x "$DOEL"/*.sh
git -C "$BRON" log -1 --format='%h %cd' --date=format:'%Y-%m-%d' > "$DOEL/versie.txt"

# Eerste direwolf.conf: de eerste USB-geluidskaart, PTT via VOX. Daarna via Zoek mijn set (tabblad Radio).
if [ ! -f "$DOEL/direwolf.conf" ]; then
  (cd "$DOEL" && python3 -c "
import ax25chat_radio as r, ax25chat_usb as u
k = next((g['kaart'] for g in u.inventaris() if g['kaart']), '')
inst = r.instellingen(); inst.update(geluidskaart=k)
r.maak_direwolf(r.station()['roepnaam'], inst)
print('   direwolf.conf: geluidskaart', k or '? (later: Zoek mijn set op het tabblad Radio)')")
fi

# ---------------------------------------------------------------------------
# 4. Diensten, rechten, wachtwoord
# ---------------------------------------------------------------------------
stap "Diensten"
plaats() { sed -e "s#@GEBRUIKER@#$GEBRUIKER#g" -e "s#@MAP@#$DOEL#g" "$1" \
             | sudo tee "/etc/systemd/system/$(basename "$1")" >/dev/null; }
for f in "$BRON"/gemeenschappelijk/diensten/*.service "$BRON"/gemeenschappelijk/diensten/*.timer "$BRON"/chat/diensten/*.service; do plaats "$f"; done

# Bijwerken en wifi wisselen vanaf de webpagina: deze scripts draaien als root, dus van root en niet te wijzigen.
# (via een tijdelijke naam + mv: dit script kan zelf het bijwerken uitvoeren dat nu loopt)
sudo install -d -m 0755 /usr/local/lib/ax25chat
for s in ax25chat-bijwerken.sh ax25chat-wifi.sh; do
  sudo install -m 0755 -o root -g root "$BRON/gemeenschappelijk/diensten/$s" "/usr/local/lib/ax25chat/.$s.nieuw"
  sudo mv -f "/usr/local/lib/ax25chat/.$s.nieuw" "/usr/local/lib/ax25chat/$s"
done
# tijdelijke sudo-regel van het bijwerken (stroom eraf tijdens bijwerken) wordt bij het opstarten opgeruimd
echo "r /etc/sudoers.d/ax25chat-bijwerken-tijdelijk" | sudo tee /etc/tmpfiles.d/ax25chat-bijwerken.conf >/dev/null

# De webpagina mag deze diensten herstarten (en Direwolf even stoppen voor de luistertest), de Pi uitzetten,
# bijwerken starten en de hotspot tijdelijk uit- en weer aanzetten
SC="$(command -v systemctl)"
REGEL="$GEBRUIKER ALL=(root) NOPASSWD: $SC restart ax25chat-rigctld, $SC restart ax25chat-direwolf"
REGEL="$REGEL, $SC stop ax25chat-direwolf, $SC start ax25chat-direwolf, $SC poweroff, $SC reboot"
REGEL="$REGEL, $SC start --no-block ax25chat-bijwerken"
REGEL="$REGEL, $SC start --no-block ax25chat-wifi@thuiswifi, $SC start --no-block ax25chat-wifi@hotspot"
TMP=$(mktemp); echo "$REGEL" > "$TMP"
sudo visudo -cf "$TMP" >/dev/null && sudo install -m 0440 "$TMP" /etc/sudoers.d/ax25chat; rm -f "$TMP"

DIENSTEN="ax25chat-rigctld ax25chat-direwolf ax25chat-web"
sudo systemctl daemon-reload
for d in $DIENSTEN; do sudo systemctl enable -q "$d"; done
sudo systemctl enable -q --now ax25chat-hotspot.timer   # bewaker: hotspot aan als de wifi nergens mee verbonden is

if [ ! -f "$DOEL/web_wachtwoord.json" ]; then
  stap "Wachtwoord voor de tabbladen Radio en Status (gebruiker: beheer)"
  until (cd "$DOEL" && python3 ax25chat_web.py --wachtwoord); do rood "   Probeer opnieuw."; done
fi

# Opdracht om later bij te werken
sudo tee /usr/local/bin/ax25chat-bijwerken >/dev/null <<EOB
#!/bin/bash
exec bash <(curl -sL $RAW/installeer.sh) "\$@"
EOB
sudo chmod +x /usr/local/bin/ax25chat-bijwerken

# Opdracht om de offline kaart via ssh te downloaden (zie docs/PROCEDURE.md, Kaart)
sudo tee /usr/local/bin/ax25chat-kaart >/dev/null <<EOB
#!/bin/bash
cd "$DOEL" && exec python3 "$DOEL/ax25chat_kaart.py" "\$@"
EOB
sudo chmod +x /usr/local/bin/ax25chat-kaart

# ---------------------------------------------------------------------------
# 5. Hotspot (als laatste; actief na herstart)
# ---------------------------------------------------------------------------
if [ "$NIEUW" = "1" ] && [ -n "$HPW" ]; then
  stap "Wifi-hotspot"
  bash "$DOEL/hotspot.sh" installeer "AX25Chat-$RN" "$HPW"
else
  stap "Wifi-hotspot"
  bash "$DOEL/hotspot.sh" repareer || rood "   Hotspot bijwerken mislukt: zie hierboven."
fi

if [ "$NIEUW" = "1" ]; then
  stap "Klaar"
  groen "   Herstart nu de Pi:  sudo reboot"
  cat <<TXT

   Na het opstarten:
   - verbind je telefoon of laptop met wifi  AX25Chat-$RN  (wachtwoord: $HPW)
   - open  http://10.42.0.1
   - tabblad Radio (gebruiker: beheer): Zoek mijn set, dan luistertest en testuitzending
   - ssh werkt via de hotspot:  ssh $GEBRUIKER@10.42.0.1
   Bijwerken: tabblad Status, knop Hotspot tijdelijk uitschakelen (de Pi gaat dan via je thuis-wifi),
   of via ssh:  ax25chat-bijwerken
TXT
else
  stap "Bijwerken: diensten herstarten"
  for d in $DIENSTEN; do sudo systemctl restart "$d" 2>/dev/null || true; done
  groen "   Bijgewerkt naar $(cat "$DOEL/versie.txt"). Instellingen zijn bewaard."
  if [ -f /var/run/reboot-required ]; then
    rood "   Er is een nieuwe kernel of systeembibliotheek geïnstalleerd: herstart de Pi (sudo reboot)."
  fi
fi
