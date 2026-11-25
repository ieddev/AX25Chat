# AX25Chat

Chatten via **AX.25 packetradio** met je telefoon of laptop. Je typt een bericht, een Raspberry Pi
met **Direwolf** maakt er packet-geluid van en je set zendt het uit. Wat binnenkomt, lees je weer
op je scherm.

```
telefoon / laptop ──wifi──► RASPBERRY PI (hotspot 10.42.0.1) ──USB──► SET ──► 2 m
                             webserver · Direwolf · rigctld
```

Onderweg met een Baofeng UV-5R, een DigiRig, een Pi Zero 2W en je telefoon, of in de shack met een
IC-9700, IC-7300 of FT-818. Eén set tegelijk, één gebruiker per Pi. Op de amateurband gaat niets
versleuteld: berichten gaan als gewone, leesbare tekst.

**Stand van zaken:** stap 1 (de Pi en de set: hotspot, Direwolf, CAT, Zoek mijn set) en stap 2 (chatten:
berichten met bevestiging, CQ roepen, monitor) zijn klaar om te testen. Stap 3 (webapp voor telefoon en
laptop, later ook een Android-app) volgt. Connected mode (BBS en nodes) komt in fase 2.

## Hoe het chatten werkt

Berichten gaan als **APRS-bericht** de lucht in, als gewone tekst. Zo kunnen ook APRSdroid, Kenwood- en
Yaesu-sets en andere APRS-stations ze lezen en beantwoorden:

```
PD3PAM-7>APZAXC::PA1ABC-9 :Hoi, hoor je me?{12      bericht aan PA1ABC-9 (nummer 12)
PA1ABC-9>APZAXC::PD3PAM-7 :ack12                     bevestiging terug
PD3PAM-7>APZAXC::CQ       :CQ CQ de PD3PAM           aan iedereen, zonder bevestiging
```

Een bericht aan een station wordt herhaald tot de bevestiging binnen is (hoogstens 5 keer, in ongeveer
6 minuten). Met **Stop** breek je dat eerder af. Langer dan 67 tekens wordt opgesplitst. Alles wat de Pi verder hoort, staat in de **Monitor**.

## Installeren

1. Zet met de **Raspberry Pi Imager** *Raspberry Pi OS Lite (64-bit)* op een SD-kaart.
   Bij *OS-instellingen bewerken*: een gebruiker, SSH aan, je wifi, tijdzone Europe/Amsterdam.
2. Start de Pi, log in (`ssh <gebruiker>@<naam>.local`) en typ:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ieddev/AX25Chat/main/installeer.sh)
```

3. Beantwoord de vragen (roepnaam met SSID, wachtwoorden) en herstart.
4. Verbind je telefoon met de wifi **AX25Chat-&lt;roepnaam&gt;** en open **http://10.42.0.1**.
   Op het tabblad **Radio** (gebruiker *beheer*): **Zoek mijn set**, daarna de **luistertest** en een
   **testuitzending**.

Bijwerken: tabblad **Status**, *AX25Chat bijwerken*. Een Pi Zero zet daarvoor even de hotspot uit en gaat via je
thuis-wifi; daarna komt de hotspot vanzelf terug. Of via ssh: `ax25chat-bijwerken`. Instellingen blijven bewaard.

De volledige procedure, met per set waar je op moet letten, staat in [docs/PROCEDURE.md](docs/PROCEDURE.md).

## Testen

Zie [docs/TESTPLAN.md](docs/TESTPLAN.md): scenario's per set voor installatie, Zoek mijn set,
frequentie, luistertest en testuitzending.

De code zelf testen, zonder hardware: `python3 -m unittest discover -s tests`.
Is Hamlib geïnstalleerd (`rigctld`), dan wordt ook het zetten van de mode op een nagebootste IC-9700 getest.

## Inhoud

| Map | Wat |
|---|---|
| `installeer.sh` | Installeert en werkt bij |
| `gemeenschappelijk/` | Set en modem: Zoek mijn set, CAT (rigctld), Direwolf, USB-herkenning, AX.25/KISS, hotspot, diensten |
| `chat/` | De chat (APRS-berichten, bevestigen, herhalen, monitor), de chatpagina en de webserver (tabbladen Chat, Radio en Status) |
| `docs/` | Procedure en testplan |
| `tests/` | Tests zonder hardware (nagebootste USB-sets) |

## Licentie en openheid

AX25Chat is open en blijft open. Wat geldt voor welk deel:

| Deel | Licentie |
|---|---|
| De AX25Chat-code (installatie, webserver, scripts) | [EUPL-1.2](LICENSE), de open-sourcelicentie van de Europese Unie, ook officieel in het Nederlands |
| `docs/` (procedure, testplan) | [CC BY-SA 4.0](docs/LICENSE) |

Iedereen mag AX25Chat gebruiken, aanpassen en doorgeven. Wie een aangepaste versie verspreidt, geeft de
broncode daarvan ook vrij, onder dezelfde licentie.

### Waar AX25Chat op voortbouwt

- [Noodnet](https://github.com/ieddev/noodnet) (EUPL-1.2): de hotspot, Direwolf, CAT en Zoek mijn set komen
  daaruit.
- [Direwolf](https://github.com/wb2osz/direwolf) (GPL-2.0) en [Hamlib](https://hamlib.github.io) (LGPL/GPL).
  Die worden bij de installatie uit de gewone pakketbronnen gehaald.

### Hoe AX25Chat gemaakt is

Gert de Haan, PD3PAM, heeft AX25Chat ontworpen, de keuzes gemaakt en test alles in de praktijk op echte
sets en Raspberry Pi's. Een groot deel van de code en documentatie is in samenwerking met een
AI-assistent (Claude, van Anthropic) geschreven. Elke wijziging wordt door hem beoordeeld en getest.
