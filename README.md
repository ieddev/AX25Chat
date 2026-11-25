# AX25Chat

Chatten via AX.25 packetradio met je telefoon of laptop. Een Raspberry Pi met **Direwolf**
maakt van je bericht packet-geluid en de set zendt het uit. Wat binnenkomt, lees je weer op je scherm.

```
telefoon / laptop ──wifi──► Raspberry Pi (hotspot 10.42.0.1) ──USB──► set
                             webserver · Direwolf · rigctld
```

Onderweg met een Baofeng UV-5R, een DigiRig, een Pi Zero 2W en je telefoon, of in de shack met een
IC-9700, IC-7300 of FT-818. Een set tegelijk, een gebruiker per Pi.

## Stand van zaken

| Stap | Wat | Stand |
|---|---|---|
| 1 | Pi: hotspot, Direwolf, CAT (rigctld), **Zoek mijn set**, profielen, luistertest, testuitzending | klaar om te testen |
| 2 | Chat-brug (APRS-berichten met bevestiging, CQ roepen) en API | volgt |
| 3 | Webapp voor telefoon en laptop (later ook als Android-app) | volgt |
| fase 2 | Connected mode (BBS en nodes, via AGW) | later |

## Installeren

1. Zet met de **Raspberry Pi Imager** *Raspberry Pi OS Lite (64-bit)* op een SD-kaart. Bij *OS-instellingen
   bewerken*: een gebruiker, SSH aan, je wifi, tijdzone Europe/Amsterdam.
2. Start de Pi, log in met ssh en typ:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ieddev/AX25Chat/main/installeer.sh)
```

3. Beantwoord de vragen (roepnaam met SSID, wachtwoord voor de hotspot en voor de beheerpagina) en herstart.
4. Verbind je telefoon met de wifi **AX25Chat-&lt;roepnaam&gt;** en open **http://10.42.0.1**.
   Op het tabblad **Radio** (gebruiker *beheer*): **Zoek mijn set**, daarna de **luistertest** en een **testuitzending**.

Bijwerken: `ax25chat-bijwerken` (instellingen blijven bewaard).

## Sets

| Set | Geluid | Besturing | Modem |
|---|---|---|---|
| Icom IC-9700 | ingebouwd (USB) | CAT via rigctld, ook PTT | 1200 baud, FM-D |
| Icom IC-7300 | ingebouwd (USB) | CAT via rigctld, ook PTT | 300 baud (HF), USB-D |
| Yaesu FT-818 + SCU-17 | SCU-17 | CAT (poort A), of RTS op poort B | 1200 baud (2 m) |
| Motorola GM-340 + DigiRig | DigiRig | PTT via RTS, geen CAT | 1200 baud |
| Baofeng UV-5R + DigiRig | DigiRig | PTT via RTS, geen CAT | 1200 baud |

**Zoek mijn set** kijkt welke geluidskaart en welke poort aan hetzelfde USB-hubje hangen. Zo weet de Pi
welke geluidskaart bij welke set hoort, en herkent hij een DigiRig (die heeft geen CAT). Icom- en
Yaesu-sets worden via CAT opgezocht. Elke gekozen set wordt bewaard als profiel; wisselen is daarna een tik.

Frequenties op 2 m: **144,850 tot 144,950 MHz** op het 12,5 kHz-raster. Bij sets zonder CAT kies je
"Zelf instellen op de set" en zet je het kanaal zelf goed. 70 cm en HF volgen later.

## Inhoud

| Bestand | Wat |
|---|---|
| `installeer.sh` | Installeert en werkt bij |
| `pi/ax25chat_web.py` | Webserver: tabbladen Chat, Radio, Status (poort 80) |
| `pi/ax25chat_radio.py` | Instellingen, profielen, direwolf.conf, Zoek mijn set, luistertest, testuitzending |
| `pi/ax25chat_usb.py` | USB-geluidskaarten en poorten vinden en per set groeperen |
| `pi/ax25chat_rig.py` | CAT via hamlib (rigctld), frequentie bewaken |
| `pi/ax25chat_ax25.py` | KISS en AX.25 UI-frames, verbinding met Direwolf |
| `pi/hotspot.sh` | Wifi-hotspot met hostapd en dnsmasq |
| `pi/diensten/` | systemd-diensten |
| `tests/` | Tests zonder hardware: `python3 -m unittest discover -s tests` |

## Licentie

[EUPL-1.2](LICENSE), net als Noodnet. Iedereen mag AX25Chat gebruiken, aanpassen en doorgeven; wie een
aangepaste versie verspreidt, geeft de broncode daarvan ook vrij.

AX25Chat bouwt voort op [Noodnet](https://github.com/ieddev/noodnet) (hotspot, Direwolf, CAT en Zoek mijn set)
en gebruikt [Direwolf](https://github.com/wb2osz/direwolf) (GPL-2.0) en [Hamlib](https://hamlib.github.io)
(LGPL/GPL) uit de gewone pakketbronnen.

Ontworpen door Gert de Haan, PD3PAM. Een groot deel van de code is in samenwerking met een AI-assistent
(Claude, van Anthropic) geschreven.
