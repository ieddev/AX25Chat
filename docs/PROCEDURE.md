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
| GM-340 + DigiRig | DigiRig, PTT via RTS | Kanaal met de packetfrequentie vooraf programmeren |
| UV-5R + DigiRig | DigiRig, PTT via RTS | TXDELAY 300-400 ms (Handmatig instellen), lage zendstand, squelch laag |

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
| MENU > SET > Connectors > **USB SEND** | **OFF** | PTT gaat via CAT |
| MENU > SET > Connectors > CI-V > **CI-V USB Port** | **Unlink from [REMOTE]** | Anders vindt Zoek mijn set de CAT niet |
| MENU > SET > Connectors > CI-V > **CI-V Address** | **A2h** (standaard) | AX25Chat gaat uit van het standaardadres |

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
- **Monitor**: alles wat de Pi hoort, ook APRS-posities en berichten tussen anderen.
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
   versturen (alleen Zenden) stuurt een Enter. **Leeg** maakt alleen het vak leeg.
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
na het verbinden in de lijst bewaard, zodat je hem de volgende keer kunt kiezen. Met **Weg** haal je de
gekozen BBS uit de lijst.

Voor de BBS-verbinding gebruikt de Pi de AGW-poort 8000 van Direwolf. Een Pi van voor deze versie zet die
poort bij de eerste start na **Bijwerken** zelf aan (Direwolf herstart dan één keer).

## APRS-baken (je positie op de kaart)

Op het tabblad **Radio** staat **APRS-baken**. Het baken zendt je positie op 144,800 MHz (de APRS-frequentie in
Europa, FM-D 1200 baud), zodat je via digipeaters en iGates op kaarten als aprs.fi verschijnt.

- **Positie**: uit een **GPS-ontvanger via USB** (een u-blox-stickje, NMEA, kost een paar tientjes), of een
  **vaste positie** die je zelf invult (breedte- en lengtegraad, bijv. 52,1234 en 6,1234). Steek de GPS in de Pi
  en druk op **Zoek GPS**. De GPS van de telefoon kan niet gebruikt worden: de browser geeft de locatie alleen
  aan beveiligde (https) pagina's.
- **Alleen als je positie verandert** (meer dan 200 m sinds het vorige baken). Tijdens het rijden elke 10, 15,
  20 of 30 minuten; met **Vaker tijdens het rijden** hoe harder je rijdt hoe vaker (tot elke 3 minuten bij
  90 km/h) en ook na een bocht. Stilstaand zendt hij niets, tenzij je **Ook stilstaand eens per uur** aanzet.
- **Altijd op 144,800**: staat de set (Station) op een andere frequentie, bijv. 144,925 om te chatten, dan zet
  de Pi hem voor het baken even op 144,800 FM-D, zendt (Direwolf wacht zelf tot het kanaal vrij is) en zet hem
  na een paar seconden terug op de frequentie en mode van ervoor. Chatberichten die in die seconden verstuurd
  moeten worden, wachten even en gaan daarna op je eigen frequentie de lucht in. Dit kan alleen:
  - met **CAT** (de Pi moet de set kunnen bedienen; met een DigiRig zonder CAT zet je Station of de set zelf op
    144,800);
  - met een set die op **2 m** kan (de IC-7300 niet);
  - als op je eigen frequentie ook **1200 baud** gebruikt wordt. Op 9600 baud (bijv. 438,175) of 300 baud (HF)
    wacht het baken, want dan zou Direwolf twee keer opnieuw moeten starten.
  Kan het niet, dan staat in de status waarom het baken wacht.
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

**Tips voor mobiel**: zet je roepnaam (Station) met **-9** erachter, bijv. PD3PAM-9; kies het symbool **Auto**;
en zet **Vaker tijdens het rijden** aan, dan wordt je spoor op de kaart mooi gelijkmatig.

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
