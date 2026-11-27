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
7. Optioneel: **APRS-baken** (je positie op de kaart), zie [APRS-baken](#aprs-baken-je-positie-op-de-kaart).

### De webpagina gebruiken: menu, meldingen en laden

- **Menu**: tik in de balk op **Radio** of **Status**. Er klapt een lijstje open met de onderdelen van die pagina
  (Radio: Station, Mijn frequenties, APRS-baken, Kaart, Set met daaronder Zoek mijn set, Mijn sets,
  Luistertest, Testuitzending en Handmatig instellen; Status: Diensten, Wifi-hotspot, Bijwerken, Log van Direwolf,
  Raspberry Pi). Tik op een onderdeel en de pagina springt er meteen naartoe. Tik ergens anders of druk op Esc om
  het lijstje te sluiten. Dit werkt op de PC en op de telefoon (op de telefoon is het lijstje schermbreed).
- **Over…** (rechts in de balk) opent een venstertje met de naam en versie van AX25Chat, de makers, het
  e-mailadres voor vragen, de licentie (EUPL-1.2), de link naar GitHub en de onderdelen van anderen die AX25Chat
  gebruikt (Direwolf, Hamlib, Leaflet, de kaart van PDOK). Sluiten met *Sluiten* of Esc.
- **Meldingen**: tik je op *Opslaan* (of een andere knop) in een onderdeel, dan verschijnt de groene (gelukt) of rode
  (fout) melding bovenin **dat onderdeel**, en blijft de pagina daar staan. Je hoeft dus niet meer terug te scrollen.
- **Sneller laden**: de pagina's Radio en Status verschijnen meteen. Wat op een Pi Zero tijd kost, komt een tel later
  vanzelf in beeld: de live gegevens van de set via CAT (frequentie, mode, S-meter), de gehoorde stations (het log van
  Direwolf over 24 uur doorzoeken) en het log op Status. Zolang staat er bijv. *De set wordt uitgelezen…*.
  Daarnaast onthoudt de Pi je inlog 12 uur (alleen in zijn geheugen); het wachtwoord controleren kost op een Pi Zero
  bijna een seconde per pagina. Wijzig je het wachtwoord (`ax25chat_web.py --wachtwoord`), dan moet iedereen opnieuw
  inloggen; na een herstart van de webserver ook.

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
| IC-7300 | CAT, geluid van de set, modem 300 baud | Alleen HF: zet je HF-frequenties bij Mijn frequenties (bijv. 14,105 USB-D 300) |
| FT-818 + SCU-17 | CAT op poort A, geluid van de SCU-17 | Vermogen is niet uit te lezen; max 6 W |
| GM-340 + DigiRig | DigiRig, PTT via RTS | Kanaal met de packetfrequentie vooraf programmeren. Geen CAT: APRS-baken alleen als de set zelf op 144,800 staat |
| UV-5R + DigiRig | DigiRig, PTT via RTS | TXDELAY 300-400 ms (Handmatig instellen), lage zendstand, squelch laag. Geen CAT: APRS-baken alleen als de set zelf op 144,800 staat |

### Instellingen op de IC-7300

Getest door PD3PAM (26-11-2026, HF packet 300 baud).

| Menu | Instelling | Waarom |
|---|---|---|
| MENU > SET > Connectors > MOD Input > **DATA MOD** | **USB** | Anders zoekt de set het geluid bij de microfoon |
| MENU > SET > Connectors > MOD Input > **USB MOD Level** | **50–70%** | Hoe hard het geluid van de Pi binnenkomt |
| MENU > SET > Connectors > **USB SEND** | **OFF** | PTT gaat via CAT; met USB SEND gaat de set soms zomaar zenden |
| MENU > SET > Connectors > CI-V > **CI-V USB Port** | **Unlink from [REMOTE]** | Anders vindt Zoek mijn set de CAT niet |
| RF POWER | bijv. **45 W** | Packet belast de eindtrap minder dan FT8, maar ga niet voluit |

**Afstellen op de ALC-meter**: zend een testuitzending (tabblad Radio) en kijk naar de ALC. Die mag net een
beetje uitslaan, niet tot het einde: dan wordt je signaal vervormd. Te weinig, ook met USB MOD Level hoog?
Zet dan op de Pi het afspeelvolume van de geluidskaart hoger: `alsamixer`, F6, kies *USB Audio CODEC*.

### Instellingen op de IC-9700

Getest door PD3PAM: CAT, frequentie en mode (FM-D en USB-D op 2 m). De geluidsinstellingen zijn
dezelfde als bij de IC-7300, maar zijn op de IC-9700 nog niet apart nagelopen.

| Menu | Instelling | Waarom |
|---|---|---|
| MENU > SET > Connectors > MOD Input > **DATA MOD** | **USB** | Anders zoekt de set het geluid bij de microfoon |
| MENU > SET > Connectors > MOD Input > **USB MOD Level** | **50%** als begin | Afstellen zoals hieronder |
| MENU > SET > Connectors > **USB SEND** | **OFF** (Pi en Linux) of **USB (B) RTS** (Windows) | Pi/Linux: PTT gaat via CAT. Windows: Direwolf kan daar niet via CAT zenden en gebruikt RTS op de tweede USB-poort (B) |
| MENU > SET > Connectors > CI-V > **CI-V USB Port** | **Unlink from [REMOTE]** | Anders vindt Zoek mijn set de CAT niet |
| MENU > SET > Connectors > CI-V > **CI-V Address** | **A2h** (standaard) | AX25Chat gaat uit van het standaardadres |

**Eén preset voor Pi en Windows?** Dat kan, met *USB SEND* op **USB (B) RTS**: op de Pi en Linux opent AX25Chat
poort B normaal nooit, dus daar verandert er niets. Eén uitzondering: **Zoek mijn set** probeert alle poorten, ook
B. Bij het openen van een poort kan RTS kort hoog worden en zendt de set even. Zet *USB SEND* dus even op OFF
voordat je op Zoek mijn set tikt (of zorg voor een antenne of dummyload), en daarna weer terug.

**Afstellen**: in FM-D let je niet op de ALC, maar op de zwaai (deviatie): stel USB MOD Level zo in dat het
tegenstation (of een tweede ontvanger) je zonder vervorming hoort; begin rond 50%. In USB-D geldt hetzelfde
als bij de IC-7300: ALC net een beetje laten uitslaan. 9600 baud (438,175) is met de IC-9700 nog niet getest.

## Chatten

Open **http://10.42.0.1** (tabblad **Chat**, zonder inloggen).

- **CQ (iedereen)**: een bericht aan iedereen. Gaat één keer de lucht in, zonder bevestiging.
- **+ Nieuw gesprek**: vul de roepnaam van het tegenstation in (met SSID als die er een heeft, bijv. PA1ABC-9).
  Je bericht wordt herhaald tot het tegenstation het bevestigt: eerst *verzonden*, dan *bevestigd ✓✓*.
  Komt er na 5 keer geen bevestiging, dan staat er *niet bevestigd* met een knop **Opnieuw**.
  Antwoordt het tegenstation niet, dan kun je het herhalen eerder afbreken met **Stop**. Komt er daarna toch nog
  een bevestiging binnen, dan staat het bericht alsnog op *bevestigd*.
- **Monitor**: alles wat de Pi hoort, ook APRS-posities en berichten tussen anderen. Als je op **Chat** tikt,
  opent de Monitor meteen, zodat je ziet wie er doorkomt. Tik op CQ of een gesprek om een bericht te sturen;
  een nieuw bericht in een gesprek zie je aan het puntje achter de naam. (Via *Bericht sturen* op de kaart
  opent meteen het gesprek met dat station.)
- **Wissen** (rechtsboven in elk scherm): maakt dat scherm leeg. Alleen de berichten gaan weg; je instellingen,
  Station en Mijn frequenties blijven staan. Een bericht dat nog verzonden of herhaald wordt, blijft staan.

Het tegenstation kan AX25Chat gebruiken, maar ook APRSdroid, een Kenwood TH-D74/TM-D710, een Yaesu met
APRS of een ander APRS-programma: die zien je bericht als gewoon APRS-bericht. Spreek dan wel dezelfde
frequentie af (bijv. 144,800 of een van de kanalen 144,850 - 144,950).

**Digipeaterpad** (tabblad Radio, Station): leeg = alleen rechtstreeks. Vul `WIDE1-1` in om via een
digipeater verder te komen. Op 144,800 doen de APRS-digipeaters dat; op de andere kanalen meestal niet.

## BBS (connected mode)

Op het tabblad **BBS** maak je verbinding met een bestaande BBS of een ander packetstation, bijvoorbeeld
PD4R-1. AX25Chat is zelf geen BBS: het is je terminal. Er is steeds één verbinding tegelijk.

1. **BBS toevoegen**: roepnaam (met SSID), een naam en de frequentie. Kies de frequentie uit de lijst; mode
   en snelheid komen van **Mijn frequenties** (tabblad Radio). Zet de frequentie van de BBS daar dus eerst
   neer, bijv. 144,925 FM-D 1200 baud. *Frequentie niet wisselen* = op de frequentie blijven die nu ingesteld is.
   Dezelfde roepnaam mag vaker in de lijst, met een andere frequentie: een node als PD4R-12 heeft ingangen op
   meerdere banden. Dezelfde roepnaam met dezelfde frequentie nog eens toevoegen vervangt de oude (bijv. om de
   naam te wijzigen).
2. **Verbinden**: kies de BBS in de keuzelijst (de laatst gekozen staat er al) en druk op Verbinden. De set gaat naar de frequentie van de BBS en de Pi maakt verbinding. Bovenaan zie je
   *Verbinden met…*, *Verbonden met…* of *Niet verbonden*. Moet Direwolf voor een andere snelheid opnieuw
   starten, dan duurt het een paar seconden langer.
3. **Terminal**: wat de BBS stuurt verschijnt in het tekstvak; wat jij stuurt staat er blauw tussen.
   Snelknoppen: **L** (lijst) en **B** (afmelden) gaan meteen; **R** (lezen), **K** (wissen) en **S** (sturen)
   zetten het commando in de invoerregel, zodat je het nummer of de roepnaam erachter typt. Een lege regel
   versturen (alleen Zenden) stuurt een Enter. **Scherm wissen** maakt alleen het vak leeg (het BBS-commando K wist een bericht op de BBS).
   De snelknoppen passen zich aan aan wat er aan de andere kant zit:
   - **Node** (bijv. PD4R-12, een BPQ-node): de knoppen komen uit het menu van de node zelf, de regel met
     de commando's achter de `}`. Bijvoorbeeld **BBS** (naar de BBS), **MHEARD** (welke stations de node
     gehoord heeft), **NODES** (andere nodes), **INFO**, **USERS**, **CHAT** en **BYE** (afmelden).
     **CONNECT** zet het commando in de invoerregel: typ de roepnaam erachter om verder te verbinden.
     Houd je vinger op een knop (of ga er met de muis op staan) voor de uitleg. De gangbare BPQ-commando's:

     | Commando | Wat het doet |
     |---|---|
     | **CONNECT** roepnaam (of **C**) | Vanaf de node verder verbinden met een ander station of een andere node |
     | **BYE** | Afmelden bij de node; de verbinding wordt verbroken |
     | **INFO** | Informatie over de node (beheerder, plaats, frequenties) |
     | **NODES** | Andere nodes die via deze node bereikbaar zijn |
     | **ROUTES** | De directe buren van de node en hoe goed de verbinding is |
     | **PORTS** | De poorten (radio's/frequenties) van de node; het nummer heb je nodig bij MHEARD |
     | **USERS** | Wie er nu met de node verbonden is |
     | **MHEARD** poortnummer | Welke stations de node op die poort de laatste tijd gehoord heeft |
     | **DX** | DX-meldingen (DX-cluster) |
     | **CHAT** | Naar de chatserver van het netwerk (verlaten met /B) |
     | **CONV** | Conferentie, een ander soort chat |
     | **BBS** / **MAIL** | Naar de BBS (post lezen en sturen) |
     | **EMAIL** | E-mail via de node (alleen als de beheerder dat heeft ingesteld) |

   - **BBS** (een prompt die eindigt op `>`): L, R, S, K en B. Kwam je via de node, dan brengt B je
     meestal terug naar de node.
   - **Chat** (de chatserver van de node): /U (wie), /H (hulp) en /B (de chat verlaten).
4. **Verbreken** (rood): verbreekt de verbinding netjes. Met **B** meld je je bij de BBS zelf af; die
   verbreekt dan zelf. Was de set voor de verbinding naar een andere frequentie gezet, dan gaat hij na het
   verbreken terug naar de frequentie van ervoor (bijv. 144,800, zodat het APRS-baken verder kan).

Antwoordt de BBS niet, dan staat er na ongeveer een halve minuut *Geen antwoord van…*. Controleer dan de
frequentie, de mode en de snelheid. Je kunt ook een roepnaam invullen die niet in je lijst staat
(**Andere roepnaam…** onderaan de keuzelijst); dan blijft de set op de huidige frequentie. Die roepnaam wordt
na het verbinden in de lijst bewaard, zodat je hem de volgende keer kunt kiezen. Met **Verwijderen** haal je de
gekozen BBS uit de lijst.

**AX.25 v2.0.** AX25Chat laat Direwolf altijd verbinden met AX.25 versie 2.0 (in direwolf.conf: `MAXV22 0`).
Versie 2.2 heeft grotere pakketvensters, maar veel nodes en BBS'en (zoals BPQ) antwoorden daar met FRMR op
(in de monitor: `SABME` en daarna `FRMR`), en de verbinding komt dan niet tot stand. Met v2.0 stuurt Direwolf
meteen `SABM` en antwoordt de node met `UA`. Een Pi met een oudere direwolf.conf krijgt deze regel vanzelf
bij de eerste start na het bijwerken.

Voor de BBS-verbinding gebruikt de Pi de AGW-poort 8000 van Direwolf. Een Pi van voor deze versie zet die
poort bij de eerste start na **Bijwerken** zelf aan (Direwolf herstart dan één keer).

## APRS-baken (je positie op de kaart)

Op het tabblad **Radio** staat **APRS-baken**. Het baken zendt je positie op 144,800 MHz (de APRS-frequentie in
Europa, FM-D 1200 baud), zodat je via digipeaters en iGates op kaarten als aprs.fi verschijnt.

- **Positie uit** (drie keuzes):
  - **GPS-ontvanger (USB)**: een u-blox-stickje (NMEA, een paar tientjes) in de Pi, en druk op **Zoek GPS**.
  - **GPS van de telefoon (app AX25Chat)**: geen stickje nodig. Zet in de Android-app bij Instellingen *Mijn
    positie naar de Pi sturen* aan; de app stuurt dan elke 10 seconden je positie, ook met het scherm uit. Een
    positie ouder dan een minuut telt niet (app dicht of buiten bereik van de hotspot): dan wacht het baken.
    Via de browser kan dit niet: die geeft de locatie alleen aan beveiligde (https) pagina's.
  - **Vaste positie**: die je zelf invult (breedte- en lengtegraad, bijv. 52,1234 en 6,1234), bijv. thuis.
- **Alleen als je positie verandert** (meer dan 200 m sinds het vorige baken). Tijdens het rijden elke 10, 15,
  20 of 30 minuten; met **Vaker tijdens het rijden** hoe harder je rijdt hoe vaker (tot elke 3 minuten bij
  90 km/h) en ook na een bocht. Stilstaand zendt hij niets, tenzij je **Ook stilstaand eens per uur** aanzet.
- **Altijd op 144,800**: staat de set (Station) op een andere frequentie, bijv. 144,925 om te chatten, dan zet
  de Pi hem voor het baken even op 144,800 FM-D, zendt (Direwolf wacht zelf tot het kanaal vrij is) en zet hem
  na een paar seconden terug op de frequentie en mode van ervoor. Chatberichten die in die seconden verstuurd
  moeten worden, wachten even en gaan daarna op je eigen frequentie de lucht in. Dit kan alleen:
  - met **CAT** (de Pi moet de set kunnen bedienen). Zie hieronder voor sets zonder CAT;
  - met een set die op **2 m** kan (de IC-7300 niet);
  - als op je eigen frequentie ook **1200 baud** gebruikt wordt. Op 9600 baud (bijv. 438,175) of 300 baud (HF)
    wacht het baken, want dan zou Direwolf twee keer opnieuw moeten starten.
  Kan het niet, dan staat in de status waarom het baken wacht.
- **Set zonder CAT** (bijv. **Baofeng UV-5R** of **Motorola GM-340** met een DigiRig): de Pi kan de frequentie
  niet veranderen, die stel je met de hand op de set in (of het kanaal is vooraf geprogrammeerd). Het baken kan dan
  **niet** aan terwijl je op een andere frequentie chat: het blijft wachten met de melding *heeft geen CAT*. Wil je
  toch een baken zenden, zet dan de set zelf op 144,800 (FM, squelch laag) en kies bij Station ook **144,800**. Dan
  zendt het baken gewoon, maar je chat en luistert dan ook op 144,800 (het APRS-kanaal; daar kun je wel
  APRS-berichten sturen en ontvangen). Een BBS op een andere frequentie bereik je zo niet: zet het baken dan uit, en
  zet de set en Station op de frequentie van de BBS.
- **Niet tijdens een BBS-verbinding**: zolang je op het tabblad BBS verbonden bent, pauzeert het baken. Na het
  verbreken gaat het verder.
- **Symbool** (auto, camper, fiets, huis …), **commentaar** (max. 40 tekens) en **pad** (standaard
  `WIDE1-1,WIDE2-1`) kun je zelf kiezen. Elk baken staat ook in de Monitor.
- **Nu een baken zenden** zendt er meteen een (handig om te testen; kijk daarna op aprs.fi).

Het is een gedeeld kanaal: zend niet vaker dan nodig.

### Hoe APRS werkt (voor nieuwe gebruikers)

144,800 MHz is in heel Europa (IARU regio 1) dezelfde APRS-frequentie. Je eigen signaal reikt mobiel zo'n 10 tot
50 km. Het wordt opgevangen door:

- **Digipeaters**: stations op hoge plekken die je pakket herhalen, zodat het verder komt. Daarvoor dient het
  pad `WIDE1-1,WIDE2-1`.
- **iGates**: stations die wat ze horen op internet zetten. Dan sta je op **aprs.fi** en kan iedereen je zien.
- **Andere APRS-stations** in de buurt, die je positie en berichten direct op hun scherm zien.

In Nederland is het netwerk van digipeaters en iGates dicht, dus onderweg kom je vrijwel altijd op aprs.fi. In
een dal of tussen hoge gebouwen kan een baken een keer gemist worden; het volgende komt dan meestal wel door.

**APRS-SSID**: hiermee krijgen het baken en je APRS-berichten een eigen SSID, terwijl BBS, node en chat je
gewone roepnaam houden. Bijvoorbeeld roepnaam (Station) **PD3PAM** en APRS-SSID **-9 auto**: op aprs.fi sta je als
PD3PAM-9, en bij PD4R-12 meld je je als PD3PAM. Berichten aan PD3PAM-9 en aan PD3PAM komen allebei binnen; de
bevestiging (ack) gaat terug van de roepnaam waaraan het bericht was. *Zelfde als roepnaam* = geen eigen SSID.

**Tips voor mobiel**: zet de APRS-SSID op **-9 auto**, kies het symbool **Auto** en zet **Vaker tijdens het
rijden** aan, dan wordt je spoor op de kaart mooi gelijkmatig.

### Wat zet je in het commentaar?

Kort en nuttig, want elk teken kost zendtijd: 20 tot 40 tekens is genoeg. Gebruikelijk is je naam en hoe je
bereikbaar bent, eventueel met de software. Bijvoorbeeld:

`Gert mobiel - QRV 144.925 - AX25Chat`

Laat persoonlijke dingen zoals je telefoonnummer of adres weg: alles wat je zendt is openbaar op aprs.fi.

### Hoe snel sta je op aprs.fi?

Hoort een iGate je baken (direct of via een digipeater), dan sta je meestal **binnen een minuut** op aprs.fi.
Zoek op je roepnaam met SSID, bijv. `PD3PAM-9`. Zie je na een paar minuten niets, dan heeft geen iGate je
gehoord: probeer een hogere plek of een betere antenne, of kijk of het baken in de Monitor staat. Onder
*raw packets* op aprs.fi zie je precies welke pakketten zijn aangekomen en via welke digipeater.

### SSID: het nummer achter je roepnaam

Met de SSID (het getal achter het streepje, 0 t/m 15) kun je meer stations met dezelfde roepnaam tegelijk in
de lucht hebben. Voor APRS zijn dit de gangbare nummers (een afspraak, geen verplichting):

| SSID | Gebruik |
|---|---|
| geen of -0 | Vast station thuis |
| -1 t/m -4 | Digipeaters, iGates en andere vaste stations |
| -5 | Smartphone-apps |
| -6 | Satelliet of speciale operaties |
| -7 | Handportofoon |
| -8 | Boot, motor of camper |
| -9 | Auto |
| -10 | Internet- of Winlink-gateway |
| -11 | Ballon of vliegtuig |
| -12 | Tracker of eenrichtingsbaken |
| -13 | Weerstation |
| -14 | Vrachtwagen |
| -15 | Overig |

Voor packet, BBS'en en nodes kiest de beheerder de nummers zelf (bijv. PD4R-1 voor een BBS en PD4R-12 voor een
node); daar zegt de SSID niets over het soort station. Gebruik je AX25Chat zowel thuis als in de auto, dan kun
je thuis zonder SSID werken en in de auto met -9.

**-0 is hetzelfde als geen SSID.** Op de lucht bestaat "PD3PAM-0" niet: dat is gewoon PD3PAM. Vul je toch -0 in,
dan haalt AX25Chat het weg (ook bij een BBS-roepnaam). Dat is nodig, want Direwolf vergelijkt roepnamen
letterlijk: verbond je als PD3PAM-0, dan herkende hij de UA van de node (gericht aan PD3PAM) niet als antwoord
en bleef hij SABM sturen tot *Failed to connect after 10 tries*.

## Kaart (gehoorde stations)

Op het tabblad **Kaart** zie je de stations die je Pi hoort met een APRS-positie: mobiele stations, digipeaters,
nodes, weerstations. Ook jezelf (groene rand), met de positie van je GPS of de vaste positie van het baken. De
kaart werkt **zonder internet**: de kaarttegels en het kaartprogramma (Leaflet) staan op de Pi.

**Waar komt de kaart vandaan?** Op het tabblad **Radio**, bij *Kaart*, kies je:

| Keuze | Uitleg |
|---|---|
| **Automatisch** (standaard) | De offline kaart waar je die hebt gedownload; daaromheen, en bij verder inzoomen, de kaart van internet (PDOK) als het apparaat waarop je kijkt internet heeft. Zonder internet zie je gewoon alleen de offline kaart. |
| **Alleen offline** | Nooit internet gebruiken, alleen de gedownloade kaart. |
| **Alleen online** | Altijd de kaart van internet, ook zonder gedownloade kaart. Handig op een PC met internet. Werkt niet op de hotspot van de Pi (daar is geen internet). |

Online haalt de browser (of het venster op de PC) de kaart zelf bij PDOK, niet de Pi. De Android-app gebruikt altijd
de offline kaart.

**Eenmalig de kaart downloaden** (met internet: thuis-wifi of netwerkkabel), op het tabblad **Radio**, onderaan bij
*Kaart*, onder *Offline kaart*:

| Keuze | Uitleg |
|---|---|
| **Midden van de kaart** | Gemeente of woonplaats, bijv. *Deventer*. Laat je hem leeg, dan neemt de Pi de vaste positie die je bij het APRS-baken invulde. |
| **Straal** | Hoe ver de kaart reikt, in elke richting. Op 2 m hoor je stations tot zo'n 50 km, via digipeaters verder. 50 km is een goede keus; 100 km geeft een veel grotere download. |
| **Detail** | *Wegen en straatnamen* (aanbevolen) of minder detail voor een kleinere download. Rond het midden (10 km) komt altijd meer detail, zodat je in je eigen buurt de straten ziet. Daaromheen ligt een grof overzicht tot zo'n 150 km. |

Met de standaardkeuze zijn het ongeveer 7.000 tegels, zo'n 100 MB, een paar minuten downloaden. De vorige kaart
blijft werken tot de nieuwe binnen is. Een afgebroken download gaat de volgende keer verder waar hij was.

**Pi Zero: hotspot óf internet.** De wifi van een Pi Zero is óf de hotspot óf verbonden met je thuis-wifi, niet
allebei. Heeft de Pi bij het downloaden geen internet, dan doet hij hetzelfde als bij het bijwerken: hotspot even
uit, verbinden met je bekende thuis-wifi, kaart downloaden, hotspot weer aan. Je telefoon of laptop raakt de
verbinding dan een paar minuten kwijt (bij 50 km ongeveer 5 tot 10 minuten); verbind daarna opnieuw met de
hotspot. Lukt de thuis-wifi niet, dan komt de hotspot meteen terug, en na 60 minuten in elk geval. Een Pi 4 met
netwerkkabel heeft internet en downloadt gewoon.

**Via ssh** kan het ook, met de opdracht `ax25chat-kaart` (als je gewone gebruiker, zonder sudo):

| Opdracht | Wat |
|---|---|
| `ax25chat-kaart Deventer` | Kaart rond Deventer, 50 km, aanbevolen detail |
| `ax25chat-kaart` | Rond de vaste positie die je bij het APRS-baken invulde |
| `ax25chat-kaart Deventer --straal 25 --zoom 13` | Kleiner gebied, minder detail (straal 25, 50, 75 of 100; zoom 12, 13 of 14) |
| `ax25chat-kaart --midden 52.255,6.163` | Rond een positie (breedte, lengte) |
| `ax25chat-kaart Deventer --schat` | Alleen laten zien hoeveel tegels en MB het wordt |
| `ax25chat-kaart --status` | Hoe staat het ervoor: huidige kaart, voortgang, of waarom het mislukte |
| `ax25chat-kaart --help` | Alle opties |

Heeft de Pi internet (netwerkkabel, of je bent via ssh op de thuis-wifi), dan zie je de voortgang in je scherm.
Zonder internet gaat hij zelf naar de thuis-wifi, zoals hierboven. Dat loopt op de achtergrond, want je
ssh-verbinding via de hotspot valt dan weg: verbind na een paar minuten opnieuw en kijk met
`ax25chat-kaart --status`. Wil je dat niet, gebruik dan `--niet-wisselen`.

**Op een pc downloaden en kopiëren** kan ook (handig met een trage of geen thuis-wifi bij de Pi). Het script is gewoon
Python zonder extra's. Op een pc met Python 3 en internet:

```bash
git clone https://github.com/ieddev/AX25Chat && cd AX25Chat/gemeenschappelijk
python3 ax25chat_kaart.py Deventer --niet-wisselen
scp -r kaart <gebruiker>@<pi>:ax25chat/
```

De map `kaart` (met `tegels` en `kaart.json`) komt zo in `~/ax25chat/` op de Pi. Laad daarna het tabblad Kaart opnieuw. De kaart is de BRT-Achtergrondkaart van het Kadaster via PDOK (open data, CC BY 4.0), dezelfde als in
Noodnet. Die dekt **alleen Nederland**: stations over de grens staan er wel op, maar zonder ondergrond.

**Op de kaart:**

| Teken | Betekenis |
|---|---|
| Blauwe rand | Direct gehoord (zonder digipeater) |
| Oranje rand | Via een digipeater gehoord; in de popup staat via welke |
| Grijs | Langer dan een uur geleden gehoord |
| Groene rand | Jij |
| Paars vierkantje ▦ met stippelvak | Alleen de locator is bekend: het station staat ergens in dat vak (zie hieronder) |
| 🚗 🏠 📡 🚶 🌤 ... | Het APRS-symbool van het station (auto, huis, digipeater, lopend, weer ...) |

Tik op een station voor de tijd, snelheid en koers, het commentaar en de positie, en **Bericht sturen** (dan opent
de chat met dat station). Met de keuzelijst bovenaan (*Toon stations van de ...*) kies je hoe ver terug: het laatste uur tot de
laatste week. De kaart past zich meteen aan en zoomt in op de stations die je dan ziet; **Toepassen** doet hetzelfde
nog een keer (handig als je intussen weggeschoven bent). Onder de keuzelijst staat wat de kleuren van de rondjes
betekenen.
Nieuwe posities komen er vanzelf bij. Een station dat langer dan een week niet gehoord is, verdwijnt.

De kaart leest de drie gangbare APRS-posities: gewone (zoals AX25Chat en APRSdroid ze zenden), gecomprimeerde
(trackers) en Mic-E (Kenwood, Yaesu en veel trackers). Objecten (zoals een evenement of een repeater die iemand
anders op de kaart zet) komen er nog niet op.

### Stations met alleen een locator (nodes en BBS'en)

Veel nodes en BBS'en (bijv. een BPQ-node zoals PD4R-12) sturen geen APRS-positie, maar wel een baken met hun
**Maidenhead-locator**, zoals `JO32CD`. Ook die stations komen op de kaart, met een **paars vierkantje** op het
midden van het locatorvak en het vak zelf als stippelrechthoek. Het is namelijk geen precieze positie: het station
staat *ergens* in dat vak.

| Locator | Grootte van het vak (in Nederland) |
|---|---|
| `JO32` (4 tekens) | ca. 135 × 110 km |
| `JO32CD` (6 tekens, het meest gebruikt) | ca. 6 × 5 km |
| `JO32CD45` (8 tekens) | ca. 600 × 460 m |

**Vanzelf uit het baken.** Staat de locator als gewone tekst in het baken (bijv. `PD4R-12 Warnsveld JO32CD 144.925`),
dan pikt de Pi hem op. Een locator van 6 of 8 tekens wordt altijd herkend; een korte van 4 tekens alleen als er
`LOC`, `LOCATOR`, `QTH` of `QRA` voor staat (anders zou bijv. *AB12* in gewone tekst ook als locator tellen).
APRS-berichten (chat) tellen niet mee: als iemand in een gesprek een locator noemt, komt hij niet op de kaart.

**Zelf invullen.** Sommige nodes zetten hun roepnaam, plaats en locator in **grote getekende letters**
(ASCII-art, verdeeld over een paar pakketjes). Die kan de Pi niet betrouwbaar lezen: elk lettertype is anders.
Vul de locator dan zelf in, onder de kaart bij **Locator per station**: roepnaam (de keuzelijst geeft de
stations die je de laatste 24 uur hoorde zonder positie), locator, **Opslaan**. Het station staat er meteen op.
Een zelf ingevulde locator gaat voor die uit het baken, en blijft staan tot je op **Verwijderen** tikt (ook als
het station een tijd niet gehoord is: dan wordt hij grijs). Je kunt ook op het vierkantje tikken en
**Locator wijzigen** kiezen. Tip: vraag de beheerder van de node om de locator ook als gewone tekst in het baken
te zetten (bij BPQ in de `BTEXT` of `IDMSG`), dan gaat het voortaan vanzelf.

**Een echte APRS-positie gaat altijd voor.** Hoort de Pi van hetzelfde station (zelfde roepnaam met SSID) een
APRS-positie, dan staat het op die precieze plek en verdwijnt het vierkantje. Let op: PD4R-12 en PD4R-9 zijn voor
de kaart twee verschillende stations.

## Android-app

De app is voor dagelijks gebruik: chatten, CQ en berichten, de kaart en de BBS. Instellen (set, roepnaam, Mijn
frequenties, BBS-lijst, baken, offline kaart) doe je eenmalig op de webpagina van de Pi, zoals hierboven.

**Installeren** (de app staat niet in de Play Store, maar op GitHub):

1. Open op je telefoon **github.com/ieddev/AX25Chat/releases** en tik bij de nieuwste versie op
   **AX25Chat-….apk**.
2. Open het gedownloade bestand. Android vraagt of je browser apps mag installeren (*onbekende bronnen* of *Apps
   van onbekende herkomst installeren*): zet dat aan voor je browser, ga terug en tik **Installeren**. Je kunt het
   daarna weer uitzetten.
3. Play Protect kan waarschuwen dat de app onbekend is: kies *Toch installeren*. De broncode staat open op GitHub.
4. Een nieuwe versie installeer je op dezelfde manier, over de oude heen. Berichten staan op de Pi, dus er gaat
   niets verloren.

**Verbinden:**

| Waar | Hoe |
|---|---|
| Onderweg | Verbind de telefoon met de wifi **AX25Chat-&lt;roepnaam&gt;** van de Pi. Meldt Android *geen internet*, kies dan **Verbonden blijven**. De app praat via de wifi met de Pi; je andere apps houden internet via 4G. Adres in de app: `10.42.0.1` (standaard). |
| Thuis | Pi en telefoon op je eigen wifi. Vul bij **Instellingen** in de app het adres in dat je router de Pi geeft (bijv. `192.168.1.50`; je ziet het in je router, of op de Pi met `hostname -I`). |

**In de app:**

| Tabblad | Wat |
|---|---|
| **Chat** | Gesprekken bovenaan (CQ, per station, Monitor), *+ Nieuw* voor een ander station. Stuur, Stop en Opnieuw werken zoals op de webpagina. Bovenaan zie je of de app verbonden is met de Pi. |
| **Kaart** | De kaart van de Pi (zie Kaart hierboven). *Bericht sturen* bij een station opent de chat in de app. |
| **BBS** | Het tabblad BBS van de Pi: keuzelijst, terminal en snelknoppen. |
| **Frequentie** (knop bovenaan) | Kies een frequentie uit Mijn frequenties (★) of de 2 m-kanalen; de Pi zet de set erop (met CAT) en Direwolf op de goede snelheid, net als bij Station op de webpagina. Zonder CAT zet je de set zelf goed. Bovenaan staat de huidige frequentie. |
| **Instellingen** | Adres van de Pi, meldingen aan of uit, *GPS van de telefoon*, de webpagina van de Pi openen, stoppen. |

**GPS van de telefoon voor het baken:**

1. In de app: Instellingen → *Mijn positie naar de Pi sturen* aan. Android vraagt toestemming voor je locatie:
   kies *Tijdens gebruik van de app*. Zet *Locatie* van Android aan.
2. Op de Pi (webpagina, tabblad Radio, APRS-baken): *Positie uit* → **GPS van de telefoon (app AX25Chat)**,
   *Baken aan*, opslaan.
3. Onder de schakelaar in de app staat wat de GPS doet (bijv. *Positie naar de Pi gestuurd*). Op de Pi zie je de
   positie bij het baken, en op het tabblad Kaart sta jij met een groene rand.

Na een herstart van de telefoon start de GPS pas weer als je de app een keer opent (een regel van Android).

**Meldingen:** de app blijft op de achtergrond verbonden met de Pi en geeft een melding bij een nieuw bericht aan
jou of aan CQ, ook met het scherm uit. Android vereist daarvoor een vaste melding *AX25Chat luistert*. Die kun je
verbergen: houd hem ingedrukt en zet *Verbinding met de Pi* uit; de meldingen voor berichten blijven werken. Ga je
buiten bereik van de hotspot of herstart de Pi, dan probeert de app het na 3 seconden opnieuw (na vijf mislukte
pogingen elke 10 seconden), en meteen zodra de wifi terugkomt. Waarom er geen verbinding is en wanneer de volgende
poging komt, zie je in Instellingen onder het adres van de Pi en in de vaste melding. Wil je helemaal stoppen:
Instellingen, *Stoppen met luisteren*.

**Voor de beheerder van de repository: een nieuwe versie uitbrengen.** GitHub bouwt de APK zelf (Actions,
*Android-app*). Eenmalig: zet bij *Settings → Secrets and variables → Actions* twee secrets:
`AX25CHAT_KEYSTORE_B64` (de inhoud van de sleutel als base64) en `AX25CHAT_KEYSTORE_WACHTWOORD`. Bewaar de sleutel
ook zelf goed: met een andere sleutel kan niemand de app nog bijwerken zonder hem eerst te verwijderen. Daarna gaat
een nieuwe versie vanzelf: verhoog het versienummer in `android/versie.txt` (bijv. van 0.2 naar 0.3) in de PR met
de wijziging. Na de merge naar main maakt GitHub zelf de tag `app-v0.3` en de release met de APK erbij (na
ongeveer twee minuten). Zonder nieuw versienummer komt er geen release, alleen een test-APK. Met de hand een tag
maken via *Releases → Draft a new release* werkt ook nog. Bij elke wijziging in `android/` bouwt GitHub ook een test-APK (onder *Actions*, bij
de run, *Artifacts*).

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

## AX25Chat op een PC (Linux)

Nog in de testfase. Je kunt AX25Chat ook zonder Pi gebruiken, op een gewone Linux-PC of laptop. De set hangt dan
met een DigiRig, een SignaLink of een eigen USB-kabel aan de PC. Voor Windows: zie het volgende hoofdstuk.

**Installeren** (Debian, Ubuntu, Linux Mint). Typ in een terminal, als gewone gebruiker:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ieddev/AX25Chat/main/installatie/linux/installeer.sh)
```

Het script installeert Direwolf, Hamlib en het eigen venster (pywebview), zet AX25Chat in `~/AX25Chat` en maakt
een snelkoppeling **AX25Chat** in het menu van je bureaublad. Zegt het script dat je uit en weer in moet loggen,
doe dat dan één keer: anders ziet AX25Chat de USB-poorten en de geluidskaart niet. Hetzelfde script nog een keer
draaien = **bijwerken**; je instellingen blijven bewaard.

**Starten:** kies **AX25Chat** in het menu, of typ `ax25chat` in een terminal. AX25Chat opent in een eigen venster
en start Direwolf (en bij CAT ook rigctld) zelf. Sluit je het venster, dan stoppen Direwolf en rigctld ook.
Lukt het eigen venster niet (pywebview ontbreekt), dan opent AX25Chat in je browser op `http://localhost:8080`.
Klik je nog een keer op het pictogram terwijl AX25Chat al draait, dan krijg je een tweede venster naar hetzelfde
programma.

Stel daarna alles in zoals op de Pi: tabblad **Radio**, roepnaam bij *Station*, dan **Zoek mijn set**.

Zonder eigen venster, alleen in de browser: `python3 ~/AX25Chat/pc/ax25chat_pc.py`. Sluit dan af met Ctrl+C.

Wat anders is dan op de Pi:

- **Geen inloggen.** De webpagina is alleen te zien op deze PC zelf, dus een wachtwoord is niet nodig.
- **Geen hotspot en geen Pi uitzetten.** Die onderdelen staan niet op het tabblad Status.
- **Instellingen apart.** Je instellingen, berichten, de kaart en het logboek van Direwolf staan in
  `~/.local/share/ax25chat`. Het tabblad Status laat zien waar precies.
- **Bijwerken:** tabblad **Status**, blok *Bijwerken*: **Controleren op nieuwe versie**, daarna **Nu bijwerken**. AX25Chat haalt de nieuwste versie van GitHub en start vanzelf opnieuw (ook Direwolf). Het installatiescript nog een keer draaien kan ook. `sudo apt update` werkt alleen Direwolf en Hamlib bij, niet AX25Chat.
- **Kaart downloaden** gaat gewoon via het internet van de PC.
- Draait er al een andere Direwolf (bijvoorbeeld voor een ander programma), sluit die dan eerst. AX25Chat gebruikt
  de poorten 8000 (AGW) en 8001 (KISS).

**Opties bij het starten** (achter `ax25chat` of achter `ax25chat_pc.py`):

| Optie | Wat het doet |
|---|---|
| `--geen-browser` | Alleen bij `ax25chat_pc.py`: start zonder de browser te openen. Open zelf `http://localhost:8080`. |
| `--poort 8090` | Een andere poort voor de webpagina, als 8080 al bezet is. |
| `--thuisnetwerk` | De PC is ook bereikbaar voor je telefoon of de Android-app op je thuisnetwerk, via `http://<adres van de PC>:8080`. Dan is wel inloggen nodig: stel eerst een wachtwoord in met `python3 ~/AX25Chat/pc/ax25chat_pc.py --wachtwoord` (gebruiker `beheer`). |
| `--wachtwoord` | Wachtwoord instellen of wijzigen voor `--thuisnetwerk`. |

## AX25Chat op Windows

Nog in de testfase. Op Windows 10 of 11 werkt AX25Chat als gewoon programma, met de set via een DigiRig, een
SCU-17 of de USB-kabel van een Icom.

**Installeren:** download `AX25Chat-setup-<versie>.exe` bij de nieuwste release met een naam die met `win-v` begint
(GitHub, *Releases*) en start het. Beheerdersrechten zijn niet nodig. Windows kan waarschuwen dat de uitgever
onbekend is: kies *Meer informatie* en *Toch uitvoeren*. Direwolf en Hamlib (rigctld) zitten in de installer; je
hoeft niets anders te installeren. Daarna staat **AX25Chat** in het Startmenu (en eventueel op het bureaublad).

**Bijwerken:** tabblad **Status**, blok *Bijwerken*: **Controleren op nieuwe versie**, daarna **Nu bijwerken**. AX25Chat downloadt de nieuwe installer, sluit en start de installer; daarna start AX25Chat vanzelf weer. Met de hand kan ook: download de nieuwe installer en installeer over de oude heen. **Verwijderen:** via Instellingen, Apps. Je
instellingen staan apart in `%APPDATA%\AX25Chat` en blijven bewaard.

Wat anders is dan op de Pi en op Linux:

- **Zoek mijn set** herkent de set aan de COM-poorten en de geluidskaart die aan hetzelfde USB-hubje hangen, net als
  op de Pi. De poorten heten hier `COM5`, `COM6` enzovoort. De geluidskaart heet zoals in Windows, bijvoorbeeld
  `USB Audio CODEC` of `2- USB PnP Sound Device`.
- **Geluidsniveaus** stel je in bij Windows: *Instellingen, Systeem, Geluid*. Kies bij *Uitvoer* de geluidskaart
  van de set voor het zendniveau (begin rond 50%) en bij *Invoer* voor het ontvangstniveau. AX25Chat heeft hier
  geen schuifjes.
- **Luistertest:** AX25Chat vraagt Direwolf om het ontvangstniveau (0 tot 100). Rond 50 is goed. Open even de
  ruisonderdrukking (squelch) van de set en tik op de knop; het duurt hooguit 10 seconden.
- **GPS-muis** voor het baken werkt op Windows nog niet. Gebruik een vaste positie of de GPS van je telefoon (app).
- **Zenden met een Icom via USB:** Direwolf voor Windows kan de set niet via CAT laten zenden (er zit geen Hamlib
  in). Frequentie en mode zet AX25Chat wel via CAT. Voor het zenden:
  - **IC-9700** (twee USB-poorten): AX25Chat gebruikt RTS op de tweede poort (B). Zet in het menu van de set
    *USB SEND* op *USB (B) RTS*.
  - **IC-7300** (één USB-poort): zet de set op *DATA VOX*, of gebruik een DigiRig.
- Het logboek van AX25Chat zelf staat in `%APPDATA%\AX25Chat\logboek\ax25chat.log`, dat van Direwolf ernaast.
- Het eigen venster gebruikt Microsoft Edge WebView2 (zit in Windows 10 en 11). Ontbreekt dat, dan opent AX25Chat
  in je browser op `http://localhost:8080`.
- **Windows Firewall** vraagt de eerste keer of Direwolf het netwerk mag gebruiken. Direwolf opent de poorten
  8000 en 8001 voor AX25Chat zelf. Je mag *Annuleren* kiezen: AX25Chat praat met Direwolf op dezelfde PC, en
  dat houdt de firewall niet tegen. Alleen als een ander programma op een andere computer Direwolf wil gebruiken,
  kies je *Toegang toestaan* (alleen privénetwerken). rigctld luistert alleen op de PC zelf en vraagt niets.
- De Radio-pagina zoekt bij de eerste keer openen de USB-apparaten op via Windows. Dat kan een paar seconden
  duren; daarna onthoudt AX25Chat het een halve minuut. **Zoek mijn set** kijkt altijd opnieuw.
- In het Startmenu staat ook **AX25Chat (in de browser)**: dat opent AX25Chat zonder eigen venster in je gewone
  browser (`AX25Chat.exe --browser`). Handig als het eigen venster niet wil.
- Is poort 8080 al in gebruik door een ander programma, dan kiest het venster vanzelf een andere vrije poort. Met
  `--thuisnetwerk` of `--poort` blijft de poort vast, want de telefoon en de app rekenen erop.
- **AX25Chat start niet of verdwijnt meteen:** start het als gewone gebruiker, niet als administrator. Kijk in
  *Taakbeheer* of er nog een `AX25Chat.exe` hangt en beëindig die. Lukt het daarna nog niet, stuur dan
  `%APPDATA%\AX25Chat\logboek\ax25chat.log` op (plak dat pad in de adresbalk van de Verkenner). Daarin staat per
  start hoe ver het kwam: *AX25Chat start*, *Webserver klaar*, *Venster openen*, *Venster geladen*. Kan AX25Chat
  echt niet starten, dan laat het ook een melding in beeld zien.

## Problemen oplossen

| Probleem | Oplossing |
|---|---|
| Hotspot niet te zien | Wacht een minuut na het opstarten; de bewaker zet hem vanzelf aan. Nog niet? `sudo systemctl status ax25chat-ap` |
| Pagina laadt niet | Ben je met de hotspot verbonden? Gebruik `http://` (niet https) |
| Zoek mijn set vindt niets | Set aan? USB-kabel goed? Bij een Icom: *CI-V USB Port* op *Unlink from [REMOTE]* |
| Set gaat niet zenden | Tabblad Status → log van Direwolf. Kijk bij Handmatig instellen naar de besturing (CAT, RTS, VOX) |
| Niets ontvangen | Luistertest doen; ontvangstniveau omhoog; staat de set op de goede frequentie? |
| App: *geen verbinding met de Pi* | Ben je met de wifi van de Pi verbonden (en *Verbonden blijven* gekozen)? Klopt het adres bij Instellingen? Thuis: het adres van de Pi op je eigen wifi. |
| App installeert niet over de oude heen | Een test-APK uit Actions heeft een andere sleutel dan een release. Verwijder de app en installeer opnieuw (berichten staan op de Pi). |
| Kaart blijft grijs | Op het tabblad Radio de offline kaart downloaden (met internet), of bij *Kaart* kiezen voor *Automatisch* of *Alleen online* als je internet hebt. Stations staan er ook zonder op. |
| Station niet op de kaart | Staat het in de Monitor? Alleen frames met een APRS-positie komen op de kaart (geen berichten of status). |
| Log bekijken via ssh | `journalctl -u ax25chat-direwolf -f` |
