"""
Een nagebootste BBS voor tests: meldt een roepnaam aan op de AGW-poort van een Direwolf en beantwoordt
de standaardcommando's (L, R n, S, K n, B) zoals een eenvoudige BBS dat doet.

    python3 nep_bbs.py 18010 PD4R-1
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gemeenschappelijk"))

import ax25chat_agw as agw  # noqa: E402

PROMPT = "PD4R BBS (L R S K B) >\r"


def main(poort, call):
    post = {1: ("PD3PAM", "Welkom", "Hallo Gert,\rWelkom op de BBS.\r/EX\r")}
    schrijven = {}                                   # tegenstation -> [stap, onderwerp, regels]

    def zeg(naar, tekst):
        link.tekst(call, naar, tekst)

    def pakket(soort, van, aan, data):
        if soort == "C":
            zeg(van, f"[PD4R-BBS-1.0]\rHallo {van}, welkom op de BBS van PD4R.\r{PROMPT}")
        elif soort == "D":
            for regel in data.decode("utf-8", "replace").replace("\n", "\r").split("\r"):
                regel = regel.strip()
                if regel or van in schrijven:
                    verwerk(van, regel)

    def verwerk(van, regel):
        if van in schrijven:
            s = schrijven[van]
            if s[0] == "onderwerp":
                s[0], s[1] = "tekst", regel
                zeg(van, "Tekst, eindig met /EX:\r")
            elif regel.upper() == "/EX":
                post[max(post) + 1 if post else 1] = (van.split("-")[0], s[1], "\r".join(s[2]) + "\r")
                del schrijven[van]
                zeg(van, "Bericht opgeslagen.\r" + PROMPT)
            else:
                s[2].append(regel)
            return
        cmd, _, arg = regel.partition(" ")
        cmd = cmd.upper()
        if cmd == "L":
            zeg(van, "Nr  Van     Onderwerp\r" + "".join(f"{n:<3} {v:<7} {o}\r" for n, (v, o, _) in sorted(post.items()))
                + PROMPT)
        elif cmd == "R" and arg.strip().isdigit() and int(arg) in post:
            v, o, t = post[int(arg)]
            zeg(van, f"Van: {v}\rOnderwerp: {o}\r\r{t}{PROMPT}")
        elif cmd == "K" and arg.strip().isdigit() and int(arg) in post:
            del post[int(arg)]
            zeg(van, f"Bericht {int(arg)} gewist.\r{PROMPT}")
        elif cmd == "S":
            schrijven[van] = ["onderwerp", "", []]
            zeg(van, "Onderwerp:\r")
        elif cmd == "B":
            zeg(van, "73, tot ziens.\r")
            time.sleep(1)
            link.verbreek(call, van)
        else:
            zeg(van, f"Onbekend commando: {regel}\r{PROMPT}")

    link = agw.AgwLink(pakket, lambda ok: ok and link.aanmelden(call), ("127.0.0.1", poort), log=lambda t: None)
    print("klaar", flush=True)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2].upper())
