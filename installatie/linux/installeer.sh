#!/bin/bash
# =============================================================================
#  AX25Chat - installeren en bijwerken op een gewone Linux-PC of laptop (zonder Pi)
#
#  Debian, Ubuntu, Linux Mint en dergelijke (apt). Als gewone gebruiker, niet met sudo:
#
#     bash <(curl -sL https://raw.githubusercontent.com/ieddev/AX25Chat/main/installatie/linux/installeer.sh)
#
#  Nog een keer draaien = bijwerken. Je instellingen (~/.local/share/ax25chat) blijven bewaard.
#  Daarna staat AX25Chat in het menu van je bureaublad, of start je het met:  ax25chat
# =============================================================================
set -e
REPO="https://github.com/ieddev/AX25Chat"
DOEL="$HOME/AX25Chat"
BIN="$HOME/.local/bin"
MENU="$HOME/.local/share/applications"

rood()  { printf '\033[1;31m%s\033[0m\n' "$*"; }
groen() { printf '\033[1;32m%s\033[0m\n' "$*"; }
stap()  { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }

[ "$(id -u)" = "0" ] && { rood "Start dit NIET met sudo, maar als gewone gebruiker."; exit 1; }
command -v apt-get >/dev/null 2>&1 || { rood "Dit script is voor Debian/Ubuntu (apt). Zie docs/PROCEDURE.md voor andere systemen."; exit 1; }

stap "Pakketten installeren (vraagt om je wachtwoord)"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 direwolf libhamlib-utils alsa-utils
# Het eigen venster (pywebview met GTK-WebKit). Lukt dat niet, dan opent AX25Chat in de browser.
VENSTER=1
if ! sudo apt-get install -y -qq python3-webview python3-gi gir1.2-webkit2-4.1 2>/dev/null; then
  if ! sudo apt-get install -y -qq python3-webview python3-gi gir1.2-webkit2-4.0 2>/dev/null; then
    VENSTER=0
    rood "   pywebview niet gevonden: AX25Chat opent straks in de browser in plaats van in een eigen venster."
  fi
fi

# Direwolf van het pakket niet automatisch laten starten: AX25Chat start zijn eigen Direwolf
sudo systemctl disable -q --now direwolf 2>/dev/null || true

stap "Toegang tot de USB-poorten en de geluidskaart"
NIEUW_GROEP=0
for g in dialout audio; do
  if ! id -nG "$USER" | grep -qw "$g"; then sudo usermod -aG "$g" "$USER"; NIEUW_GROEP=1; fi
done

stap "AX25Chat ophalen van GitHub naar $DOEL"
if [ -d "$DOEL/.git" ]; then
  git -C "$DOEL" fetch -q origin main && git -C "$DOEL" reset -q --hard origin/main
else
  git clone -q "$REPO" "$DOEL"
fi
echo "   versie: $(git -C "$DOEL" log -1 --format='%h %cd' --date=format:'%Y-%m-%d %H:%M')"
mkdir -p "$HOME/.local/share/ax25chat"
git -C "$DOEL" log -1 --format="%h %cd" --date=format:"%Y-%m-%d" > "$HOME/.local/share/ax25chat/versie.txt"

stap "Snelkoppeling in het menu en de opdracht 'ax25chat'"
mkdir -p "$BIN" "$MENU"
cat > "$BIN/ax25chat" <<SCRIPT
#!/bin/sh
exec python3 "$DOEL/pc/ax25chat_venster.py" "\$@"
SCRIPT
chmod +x "$BIN/ax25chat"
cat > "$MENU/ax25chat.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=AX25Chat
Comment=Packet-radio chat, BBS en APRS via Direwolf
Exec=python3 "$DOEL/pc/ax25chat_venster.py"
Icon=$DOEL/pc/ax25chat.svg
Terminal=false
Categories=HamRadio;Network;Chat;
DESKTOP
update-desktop-database "$MENU" 2>/dev/null || true

groen ""
groen "AX25Chat is geïnstalleerd."
echo "   Starten: AX25Chat in het menu, of typ  ax25chat"
[ "$VENSTER" = "0" ] && echo "   (opent in de browser: http://localhost:8080)"
[ "$NIEUW_GROEP" = "1" ] && rood "   Log één keer uit en weer in (of herstart), anders ziet AX25Chat de USB-poorten en geluidskaart niet."
echo "   Uitleg: $DOEL/docs/PROCEDURE.md, deel 'AX25Chat op een PC'."
