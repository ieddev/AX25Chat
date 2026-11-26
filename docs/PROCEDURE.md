# AX25Chat - een Pi opzetten

Met deze procedure zet je een Raspberry Pi (Zero 2W of 4) op als AX25Chat-station: een eigen
wifi-hotspot, Direwolf als modem en je set via USB. Daarna open je op je telefoon of laptop
**http://10.42.0.1**.

Wat je nodig hebt:

- Raspberry Pi Zero 2W (onderweg) of Pi 4 (shack), met voeding en een SD-kaart van minstens 16 GB
- een set met USB-aansluiting: IC-9700, IC-7300, FT-818 met SCU-17, of een set met een DigiRig
  (bijv. GM-340 of UV-5R)
- voor de eerste installatie: internet via wifi of netwerkkabel
- de juiste **USB-kabel** tussen set (of DigiRig/SignaLink) en Pi: zie [Kabels](#kabels)

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

1. Sluit de set aan via USB, met de kabel uit [Kabels](#kabels) (bij een DigiRig: de DigiRig aan de Pi en de kabel van de DigiRig naar de set).
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
3. **Station**: controleer je roepnaam en kies de frequentie (144,800 APRS, of 144,850 - 144,950 MHz). Heeft de set geen
   CAT (DigiRig), of gebruik je een andere band? Kies *Zelf instellen op de set*.
   **Mode** (alleen met CAT): *Automatisch* zet de set in FM-D (op HF in USB-D). Kies je een frequentie uit Mijn
   frequenties met een eigen mode, dan geldt die mode en doet deze keuzelijst niet mee. Packet met 1200 baud op 2 m is
   FM-D; kies USB-D alleen als het tegenstation SSB-packet gebruikt. Draait iemand aan de set, dan zet de Pi
   frequentie en mode binnen een minuut terug.
   **Mijn frequenties**: voeg frequenties van stations, bakens en BBS'en bij jou in de buurt toe, elk met mode en
   snelheid (bijv. 144,775 USB-D, of 438,175 FM-D 9600 baud). Ze staan daarna in de lijst bij Station. Met
   Mode en Modem op *Automatisch* neemt de Pi de mode en snelheid van die frequentie over. 9600 baud werkt alleen
   met een set die daarvoor een aansluiting heeft; HF alleen met een HF-set (IC-7300, FT-818).
4. **Zoek mijn set**. Lees eerst de oranje waarschuwing (bij een Icom: *USB SEND* = OFF). De Pi toont
   wat hij gevonden heeft. Geef de set een naam (bijv. *UV-5R onderweg*) en tik op **Gebruiken en bewaren**.
5. **Luistertest**: open de ruisonderdrukking (squelch) van de set en tik op *Luister 5 seconden*.
   Het advies zegt of het ontvangstniveau goed is.
6. **Testuitzending**: tik op *Opslaan + testuitzending*. De set moet kort gaan zenden. Luister op een
   tweede ontvanger: schoon packet-geluid, niet vervormd. Pas het zendniveau aan en test opnieuw.

## Kabels

De aansluiting op de set verschilt per set, en de Pi Zero 2W heeft een andere aansluiting dan de
Pi 3, 4 en 5. Gebruik altijd een **datakabel**: een kabel die alleen kan laden werkt niet (de Pi ziet
de set dan niet).

| Set of interface | Aansluiting | Pi 3 / 4 / 5 (USB-A) | Pi Zero 2W (micro-USB) |
|---|---|---|---|
| Icom IC-9700, IC-7300, IC-7100 | USB-B | USB-A naar USB-B ("printerkabel") | micro-USB naar USB-B |
| Icom IC-705 | micro-USB | USB-A naar micro-USB | micro-USB naar micro-USB (OTG-kabel) |
| Yaesu SCU-17 (FT-817/818) | USB-B | USB-A naar USB-B | micro-USB naar USB-B |
| DigiRig Mobile | USB-C | USB-A naar USB-C | micro-USB naar USB-C (OTG-kabel) |
| SignaLink USB | USB-B | USB-A naar USB-B | micro-USB naar USB-B |

**Pi Zero 2W:**

- De Zero heeft twee micro-USB-poorten. De buitenste (**PWR IN**, bij de hoek) is alleen voor de voeding.
  De set gaat op de binnenste (**USB**).
- Geen kabel met micro-USB aan één kant? Een **OTG-verloopje** (micro-USB stekker naar USB-A bus) met de
  gewone kabel van de Pi 4-kolom werkt ook.
- Meer dan één apparaat tegelijk (bijv. een set en een USB-stick) kan alleen via een klein **USB-hubje**
  op de USB-poort; liefst een hubje met eigen voeding.

**Storing (RF in de USB-kabel):** houd de kabel kort en klik er aan beide kanten een **ferrietkern**
omheen, zeker bij HF of bij een portofoon dicht bij de antenne. Valt de verbinding weg tijdens het zenden,
dan is dat bijna altijd RF in de kabel of de voeding.

## Sets

| Set | Wat Zoek mijn set vindt | Let op |
|---|---|---|
| IC-9700 | CAT op poort A, geluid van de set | *MENU > SET > Connectors > USB SEND* op **OFF** (PTT gaat via CAT) |
| IC-7300 | CAT, geluid van de set, modem 300 baud | Alleen HF: kies bij Station *Zelf instellen op de set* |
| FT-818 + SCU-17 | CAT op poort A, geluid van de SCU-17 | Vermogen is niet uit te lezen; max 6 W |
| GM-340 + DigiRig | DigiRig, PTT via RTS | Kanaal met de packetfrequentie vooraf programmeren |
| UV-5R + DigiRig | DigiRig, PTT via RTS | TXDELAY 300-400 ms (Handmatig instellen), lage zendstand, squelch laag |

## Chatten

Open **http://10.42.0.1** (tabblad **Chat**, zonder inloggen).

- **CQ (iedereen)**: een bericht aan iedereen. Gaat één keer de lucht in, zonder bevestiging.
- **+ Nieuw gesprek**: vul de roepnaam van het tegenstation in (met SSID als die er een heeft, bijv. PA1ABC-9).
  Je bericht wordt herhaald tot het tegenstation het bevestigt: eerst *verzonden*, dan *bevestigd ✓✓*.
  Komt er na 5 keer geen bevestiging, dan staat er *niet bevestigd* met een knop **Opnieuw**.
  Antwoordt het tegenstation niet, dan kun je het herhalen eerder afbreken met **Stop**. Komt er daarna toch nog
  een bevestiging binnen, dan staat het bericht alsnog op *bevestigd*.
- **Monitor**: alles wat de Pi hoort, ook APRS-posities en berichten tussen anderen.
- **Wissen** (rechtsboven in elk scherm): maakt dat scherm leeg. Alleen de berichten gaan weg; je instellingen,
  Station en Mijn frequenties blijven staan. Een bericht dat nog verzonden of herhaald wordt, blijft staan.

Het tegenstation kan AX25Chat gebruiken, maar ook APRSdroid, een Kenwood TH-D74/TM-D710, een Yaesu met
APRS of een ander APRS-programma: die zien je bericht als gewoon APRS-bericht. Spreek dan wel dezelfde
frequentie af (bijv. 144,800 of een van de kanalen 144,850 - 144,950).

**Digipeaterpad** (tabblad Radio, Station): leeg = alleen rechtstreeks. Vul `WIDE1-1` in om via een
digipeater verder te komen. Op 144,800 doen de APRS-digipeaters dat; op de andere kanalen meestal niet.

## Wisselen van set

Sluit de andere set aan en kies op het tabblad Radio bij **Mijn sets** het profiel en *Gebruiken*.
Een nieuwe set? Doe **Zoek mijn set** opnieuw.

## Bijwerken

Bijwerken heeft internet nodig. Een Pi Zero 2W heeft alleen wifi, en die wifi is normaal de hotspot. Daarom zet
je de hotspot even uit en gaat de Pi via je thuis-wifi (de wifi die je in de Raspberry Pi Imager hebt ingevuld).

**Via de webpagina** (tabblad **Status**, blok *AX25Chat bijwerken*):

1. **Hotspot tijdelijk uitschakelen**, daarna **Hotspot uit, thuis-wifi aan**. Je telefoon verliest de verbinding.
2. Verbind je telefoon met je thuis-wifi en open `http://<naam van de Pi>.local` (bijvoorbeeld
   `http://ax25chat.local`). Lukt dat niet: zoek het adres van de Pi in je router.
3. Tabblad Status: je ziet *Thuis-wifi actief*. Kies **Controleren op nieuwe versie**, daarna **Nu bijwerken**.
   De voortgang staat op het scherm (op een Pi Zero 5 tot 15 minuten).
4. Klaar: de hotspot gaat na 1 minuut vanzelf weer aan. Verbind je telefoon weer met **AX25Chat-&lt;roepnaam&gt;**.

Vangnetten: lukt de thuis-wifi niet, dan staat de hotspot binnen 2 minuten weer aan. Na een uur, en na een
herstart, staat de hotspot altijd weer aan. Met **Hotspot nu weer aanzetten** kun je ook zonder bijwerken terug.

**Via ssh** (bijvoorbeeld met een netwerkkabel aan een Pi 4): typ `ax25chat-bijwerken`.

Instellingen, profielen en berichten blijven bewaard.

**Eén keer nodig:** was de Pi geïnstalleerd vóór er een bijwerkknop was, dan werkt de knop pas na één keer
bijwerken via ssh. Verbind je telefoon met de hotspot en log in met `ssh <gebruiker>@10.42.0.1`, dan:

```bash
~/ax25chat/hotspot.sh thuiswifi     # de ssh-verbinding valt weg; de Pi gaat naar je thuis-wifi
```

Verbind je laptop met de thuis-wifi, log opnieuw in met `ssh <gebruiker>@<naam>.local` en typ `ax25chat-bijwerken`.
Daarna `sudo reboot`: de hotspot is terug en de knop werkt voortaan.

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
