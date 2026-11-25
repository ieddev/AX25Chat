# AX25Chat - een Pi opzetten

Met deze procedure zet je een Raspberry Pi (Zero 2W of 4) op als AX25Chat-station: een eigen
wifi-hotspot, Direwolf als modem en je set via USB. Daarna open je op je telefoon of laptop
**http://10.42.0.1**.

Wat je nodig hebt:

- Raspberry Pi Zero 2W (onderweg) of Pi 4 (shack), met voeding en een SD-kaart van minstens 16 GB
- een set met USB-aansluiting: IC-9700, IC-7300, FT-818 met SCU-17, of een set met een DigiRig
  (bijv. GM-340 of UV-5R)
- voor de eerste installatie: internet via wifi of netwerkkabel
- bij een Pi Zero 2W met meer dan één USB-apparaat: een klein USB-hubje

## Stap 1 - SD-kaart maken

1. Start de **Raspberry Pi Imager** op je pc.
2. Kies je Pi en **Raspberry Pi OS Lite (64-bit)**.
3. Bij *OS-instellingen bewerken*:
   - een gebruikersnaam en wachtwoord (bijv. `ax25chat`)
   - **SSH aan**
   - je thuis-wifi (voor de installatie)
   - tijdzone **Europe/Amsterdam**, toetsenbord **us**
4. Schrijf de kaart en zet hem in de Pi.

## Stap 2 - Aansluiten en opstarten

1. Sluit de set aan via USB (bij een DigiRig: de DigiRig aan de Pi en de kabel naar de set).
2. Zet de set aan en start de Pi. De eerste start duurt een paar minuten.
3. Log in vanaf je pc: `ssh ax25chat@<naam>.local` (of zoek het adres op in je router).

## Stap 3 - Installeren

Typ op de Pi:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ieddev/AX25Chat/main/installeer.sh)
```

De installatie vraagt:

- je **roepnaam met SSID** (bijv. `PD3PAM-7`)
- een **wachtwoord voor de hotspot** (Enter = de Pi kiest er een; schrijf het op)
- een **wachtwoord voor de beheerpagina** (gebruiker `beheer`, tabbladen Radio en Status)

Herstart daarna: `sudo reboot`. Na de herstart staat de hotspot **AX25Chat-&lt;roepnaam&gt;** aan;
de Pi zit dan niet meer op je thuis-wifi.

## Stap 4 - Instellen via de webpagina

1. Verbind je telefoon of laptop met de wifi **AX25Chat-&lt;roepnaam&gt;**. Android meldt "geen internet":
   kies *Verbonden blijven*.
2. Open **http://10.42.0.1** en ga naar het tabblad **Radio** (gebruiker `beheer`).
3. **Station**: controleer je roepnaam en kies de frequentie (144,850 - 144,950 MHz). Heeft de set geen
   CAT (DigiRig), of gebruik je een andere band? Kies *Zelf instellen op de set*.
4. **Zoek mijn set**. Lees eerst de oranje waarschuwing (bij een Icom: *USB SEND* = OFF). De Pi toont
   wat hij gevonden heeft. Geef de set een naam (bijv. *UV-5R onderweg*) en tik op **Gebruiken en bewaren**.
5. **Luistertest**: open de ruisonderdrukking (squelch) van de set en tik op *Luister 5 seconden*.
   Het advies zegt of het ontvangstniveau goed is.
6. **Testuitzending**: tik op *Opslaan + testuitzending*. De set moet kort gaan zenden. Luister op een
   tweede ontvanger: schoon packet-geluid, niet vervormd. Pas het zendniveau aan en test opnieuw.

## Sets

| Set | Wat Zoek mijn set vindt | Let op |
|---|---|---|
| IC-9700 | CAT op poort A, geluid van de set | *MENU > SET > Connectors > USB SEND* op **OFF** (PTT gaat via CAT) |
| IC-7300 | CAT, geluid van de set, modem 300 baud | Alleen HF: kies bij Station *Zelf instellen op de set* |
| FT-818 + SCU-17 | CAT op poort A, geluid van de SCU-17 | Vermogen is niet uit te lezen; max 6 W |
| GM-340 + DigiRig | DigiRig, PTT via RTS | Kanaal met de packetfrequentie vooraf programmeren |
| UV-5R + DigiRig | DigiRig, PTT via RTS | TXDELAY 300-400 ms (Handmatig instellen), lage zendstand, squelch laag |

## Wisselen van set

Sluit de andere set aan en kies op het tabblad Radio bij **Mijn sets** het profiel en *Gebruiken*.
Een nieuwe set? Doe **Zoek mijn set** opnieuw.

## Bijwerken

De Pi heeft internet nodig. Twee manieren:

- netwerkkabel (Pi 4), of
- tijdelijk de thuis-wifi: `~/ax25chat/hotspot.sh thuiswifi` (tot de volgende herstart)

Typ dan `ax25chat-bijwerken`. Instellingen en profielen blijven bewaard.

## Uitzetten

Tabblad **Status** → *Pi uitschakelen*. Wacht tot het groene lampje niet meer knippert (± 20 seconden)
en haal dan pas de stroom eraf.

## Problemen oplossen

| Probleem | Oplossing |
|---|---|
| Hotspot niet te zien | Wacht een minuut na het opstarten; de bewaker zet hem vanzelf aan. Nog niet? `sudo systemctl status ax25chat-ap` |
| Pagina laadt niet | Ben je met de hotspot verbonden? Gebruik `http://` (niet https) |
| Zoek mijn set vindt niets | Set aan? USB-kabel goed? Bij een Icom: *CI-V USB Port* op *Unlink from [REMOTE]* |
| Set gaat niet zenden | Tabblad Status → log van Direwolf. Kijk bij Handmatig instellen naar de besturing (CAT, RTS, VOX) |
| Niets ontvangen | Luistertest doen; ontvangstniveau omhoog; staat de set op de goede frequentie? |
| Log bekijken via ssh | `journalctl -u ax25chat-direwolf -f` |
