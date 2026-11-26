# AX25Chat - testplan

Volg de scenario's per set. Vink af wat werkt en noteer wat anders gaat dan verwacht (wat je zag,
met welke set, hoe laat). A tot en met E gaan over de Pi en de set (stap 1), F over het chatten (stap 2).

Handig tijdens het testen: tabblad **Status** (log van Direwolf onderaan) open op een tweede apparaat,
en een tweede ontvanger op dezelfde frequentie.

## A. Installatie en hotspot

| # | Scenario | Hoe | Verwacht | OK |
|---|---|---|---|---|
| A1 | Installatie | `installeer.sh` op een verse Pi | Vragen naar roepnaam en wachtwoorden; eindigt met "Klaar" | ☐ |
| A2 | Hotspot | Herstart; zoek wifi op de telefoon | **AX25Chat-&lt;roepnaam&gt;** zichtbaar, verbinden lukt | ☐ |
| A3 | Webpagina | Open http://10.42.0.1 | Tabblad Chat zonder inloggen | ☐ |
| A4 | Inloggen | Tabblad Radio | Vraagt gebruiker `beheer` en wachtwoord | ☐ |
| A5 | Laptop | Laptop met de hotspot verbinden, http://10.42.0.1 | Zelfde pagina's | ☐ |
| A6 | Bijwerken | `hotspot.sh thuiswifi`, dan `ax25chat-bijwerken` | Bijgewerkt; instellingen en profielen bewaard | ☐ |
| A7 | Hotspot uit | Status → Hotspot tijdelijk uitschakelen → Hotspot uit, thuis-wifi aan | Pi op de thuis-wifi; Status toont *Thuis-wifi actief* en het adres | ☐ |
| A8 | Bijwerken via de knop | Na A7: Controleren op nieuwe versie, Nu bijwerken | Voortgang loopt, eindigt met *Klaar*; hotspot na 1 minuut terug | ☐ |
| A9 | Thuis-wifi mislukt | Thuis-wifi-router uit, dan A7 | Hotspot binnen 2 minuten terug | ☐ |
| A10 | Terug zonder bijwerken | Na A7: Hotspot nu weer aanzetten | Hotspot binnen een halve minuut terug | ☐ |
| A11 | Herstart op thuis-wifi | Na A7: Pi herstarten (stroom eraf en erop) | Hotspot is na het opstarten weer aan | ☐ |

## B. Zoek mijn set

| # | Set | Hoe | Verwacht | OK |
|---|---|---|---|---|
| B1 | IC-9700 | *USB SEND* = OFF, Zoek mijn set | "Icom IC-9700", CAT gevonden, geluidskaart CODEC | ☐ |
| B2 | IC-7300 | Zoek mijn set | "Icom IC-7300", CAT gevonden, modem 300 baud | ☐ |
| B3 | FT-818 + SCU-17 | Zoek mijn set | Yaesu FT-818, CAT op poort A (niet poort B) | ☐ |
| B4 | GM-340 + DigiRig | Zoek mijn set | "DigiRig", PTT via RTS, geen CAT geprobeerd | ☐ |
| B5 | UV-5R + DigiRig | Zoek mijn set | Idem B4 | ☐ |
| B6 | Twee sets tegelijk | IC-9700 en DigiRig samen aan de Pi | Twee voorstellen, elk met de eigen geluidskaart | ☐ |
| B7 | Set uit | Zoek met de Icom uitgeschakeld | Voorstel met RTS en de uitleg dat CAT niet antwoordde | ☐ |

## C. Frequentie en CAT

| # | Scenario | Hoe | Verwacht | OK |
|---|---|---|---|---|
| C1 | Frequentie zetten | Station: 144,875 MHz, opslaan (IC-9700) | Set springt naar 144,875 in datamode | ☐ |
| C2 | Bewaker | Draai aan de VFO van de IC-9700 | Binnen een minuut terug op de ingestelde frequentie | ☐ |
| C3 | IC-7300 op 2 m | Frequentie 144,900 met de IC-7300 | Melding dat de IC-7300 dat niet kan | ☐ |
| C1b | Mode | IC-9700 met de hand op USB-D zetten (Mode: Automatisch, 144,925) | Binnen een minuut terug op FM-D; tabblad Radio toont FM-D ✓ | ☐ |
| C1c | Mode zelf kiezen | Station: Mode USB-D, opslaan | Set gaat naar USB-D en blijft daar | ☐ |
| C5 | Mijn frequenties | Radio → Mijn frequenties: 144,775 USB-D toevoegen, bij Station kiezen, opslaan (IC-9700) | Set naar 144,775 in USB-D | ☐ |
| C6 | 9600 baud | 438,175 FM-D 9600 toevoegen en kiezen | Direwolf herstart met MODEM 9600 (Status-log) | ☐ |
| C4 | Zelf instellen | Station: *Zelf instellen op de set* | Pi laat de frequentie met rust | ☐ |

## D. Luistertest en testuitzending

| # | Set | Hoe | Verwacht | OK |
|---|---|---|---|---|
| D1 | elke set | Squelch open, Luister 5 seconden | "Er komt geluid van de set binnen" | ☐ |
| D2 | elke set | Volume dicht of verkeerde geluidskaart | "Er komt (bijna) geen geluid binnen" | ☐ |
| D3 | elke set | Opslaan + testuitzending | Set zendt kort; tweede ontvanger hoort packet | ☐ |
| D4 | elke set | Lang (6 s) | Set zendt ongeveer 6 seconden | ☐ |
| D5 | elke set | Een ander station zendt een packet | Station staat bij *Gehoorde stations* met niveau rond 50 | ☐ |

## E. Mijn sets

| # | Scenario | Hoe | Verwacht | OK |
|---|---|---|---|---|
| E1 | Profiel bewaren | Na B1 en B5 | Beide in de lijst Mijn sets | ☐ |
| E2 | Wisselen | UV-5R aansluiten, profiel *Gebruiken* | Direwolf herstart met de DigiRig; testuitzending werkt | ☐ |
| E3 | Set niet aangesloten | Profiel gebruiken zonder de set | Waarschuwing "niet aangesloten" | ☐ |
| E4 | Na herstart | Pi herstarten | Laatst gekozen set is nog actief | ☐ |

## F. Chatten

Nodig: een tegenstation. Dat kan een tweede AX25Chat-Pi zijn, of een telefoon met APRSdroid (met een
TNC of via geluid), of een set met APRS-berichten. Spreek een frequentie af.

| # | Scenario | Hoe | Verwacht | OK |
|---|---|---|---|---|
| F1 | CQ roepen | Chat → CQ (iedereen), typ een bericht, Zenden | Set zendt één keer; tegenstation ziet het bericht aan CQ | ☐ |
| F2 | CQ ontvangen | Tegenstation stuurt een bericht aan CQ | Verschijnt bij CQ (iedereen), met de roepnaam erboven | ☐ |
| F3 | Bericht met bevestiging | + Nieuw gesprek, roepnaam tegenstation, bericht sturen | Eerst *verzonden*, na de ack *bevestigd ✓✓* | ☐ |
| F4 | Bericht ontvangen | Tegenstation stuurt een bericht aan mijn roepnaam (met SSID) | Verschijnt in het gesprek; tegenstation krijgt een bevestiging | ☐ |
| F5 | Geen antwoord | Bericht aan een roepnaam die niet in de lucht is | 5 keer herhaald, daarna *niet bevestigd* en knop Opnieuw | ☐ |
| F5b | Herhalen stoppen | Bericht aan een roepnaam die niet antwoordt, dan **Stop** | Niet meer herhaald; *gestopt, niet bevestigd* en knop Opnieuw | ☐ |
| F6 | Lang bericht | Bericht van meer dan 67 tekens | Opgesplitst in delen, elk bevestigd | ☐ |
| F7 | APRSdroid | Bericht van en naar APRSdroid | Beide kanten zien het bericht en de bevestiging | ☐ |
| F8 | Monitor | Op 144,800 luisteren | APRS-verkeer verschijnt in de Monitor | ☐ |
| F9 | Telefoon en laptop tegelijk | Beide de chatpagina open | Een bericht verschijnt op beide meteen | ☐ |
| F10 | Na herstart | Pi herstarten, chatpagina openen | Eerdere berichten staan er nog | ☐ |
| F11 | Digipeater | Station: pad `WIDE1-1`, bericht op 144,800 | In de Monitor komt het bericht terug met `WIDE1-1*` (niet als nieuw bericht) | ☐ |
| F12 | Wissen | In een gesprek, CQ en de Monitor op **Wissen** drukken en bevestigen | Dat scherm is leeg (ook op een tweede telefoon); de andere schermen, Station en Mijn frequenties zijn onveranderd | ☐ |

## G. BBS (connected mode)

| # | Wat | Hoe | Verwacht | OK |
|---|-----|-----|----------|----|
| G1 | BBS toevoegen | Radio: Mijn frequenties 144,925 FM-D 1200. BBS: PD4R-1 met die frequentie | PD4R-1 staat in de lijst met *144,925 MHz · FM-D · 1200 baud* | ☐ |
| G2 | Verbinden | Op 144,900: PD4R-1 kiezen in de keuzelijst, Verbinden | Set gaat naar 144,925; *Verbonden met PD4R-1*; welkomsttekst van de BBS | ☐ |
| G3 | Lijst en lezen | L, daarna R en een nummer | Lijst met berichten, daarna het bericht | ☐ |
| G4 | Afmelden | B | BBS zegt gedag en verbreekt; *Niet verbonden* | ☐ |
| G5 | Verbreken | Opnieuw verbinden, dan de rode knop Verbreken | Na een paar seconden *Niet verbonden* | ☐ |
| G6 | Geen antwoord | Verbinden met een roepnaam die er niet is | Na ongeveer een halve minuut *Geen antwoord van…* | ☐ |
| G7 | Andere snelheid | BBS op 438,175 (9600, Mijn frequenties) | Direwolf herstart, daarna wordt er verbonden | ☐ |
| G8 | Oude Pi | Pi van voor deze versie: Bijwerken | Direwolf herstart één keer; BBS-verbinding werkt | ☐ |
| G9 | Node | Verbinden met PD4R-12 | Knoppen *Node*: CONNECT, BYE, INFO, NODES, … zoals in de prompt | ☐ |
| G10 | Node → BBS → node | BBS, daarna B | Knoppen wisselen naar L, R, S, K, B en daarna terug naar de node-knoppen | ☐ |
| G11 | Chat | CHAT, daarna /B | Knoppen /U, /H, /B; na /B weer de node-knoppen | ☐ |
| G12 | Nieuwe roepnaam | Keuzelijst: *Andere roepnaam…*, PD4R-12 invullen, Verbinden | Na het verbinden staat PD4R-12 in de keuzelijst; na herladen van de pagina staat de laatst gekozen BBS al gekozen | ☐ |
