# AX25Chat - testplan stap 1 (radio)

Volg de scenario's per set. Vink af wat werkt en noteer wat anders gaat dan verwacht (wat je zag,
met welke set, hoe laat). Het chatten zelf komt in stap 2; dit testplan gaat over de Pi en de set.

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
