"""
Nagebootste IC-9700 (CI-V) op een pty, voor tests met de echte rigctld (Hamlib).

    python3 nep_ic9700.py [--weiger-26]

Schrijft de naam van de pty op de eerste regel en antwoordt daarna op CI-V. Met --weiger-26 weigert de set
het modecommando 0x26 (zoals een IC-9700 dat soms doet); Hamlib 4.5 verandert dan alleen de datamode.
"""

import os
import pty
import sys
import tty

ADRES = 0xA2
stand = {"freq": 144900000, "mode": 0x05, "data": 1, "filter": 1}     # 144,900 FM-D
WEIGER_26 = "--weiger-26" in sys.argv
LOG = open(os.environ["NEP_LOG"], "a") if os.environ.get("NEP_LOG") else None


def naar_bcd(f):
    s = f"{f:010d}"
    return bytes(int(s[i - 2]) << 4 | int(s[i - 1]) for i in range(10, 0, -2))


def van_bcd(b):
    return int("".join(f"{x >> 4}{x & 15}" for x in reversed(b)))


def antwoord(cmd, data):
    if cmd == 0x03:
        return bytes([0x03]) + naar_bcd(stand["freq"])
    if cmd == 0x05:
        stand["freq"] = van_bcd(data)
    elif cmd == 0x25:
        if len(data) == 1:
            return bytes([0x25, data[0]]) + naar_bcd(stand["freq"])
        stand["freq"] = van_bcd(data[1:])
    elif cmd == 0x04:
        return bytes([0x04, stand["mode"], stand["filter"]])
    elif cmd == 0x06:
        stand["mode"] = data[0]
    elif cmd == 0x1A and data[:1] == b"\x06":
        if len(data) == 1:
            return bytes([0x1A, 0x06, stand["data"], stand["filter"]])
        stand["data"] = data[1]
    elif cmd == 0x26:
        if len(data) == 1:
            return bytes([0x26, data[0], stand["mode"], stand["data"], stand["filter"]])
        if WEIGER_26:
            return b"\xfa"
        stand["mode"], stand["data"] = data[1], data[2]
    elif cmd == 0x19:
        return bytes([0x19, 0x00, ADRES])
    elif cmd == 0x1C and data == b"\x00":
        return bytes([0x1C, 0x00, 0x00])
    return b"\xfb"


def main():
    meester, slaaf = pty.openpty()
    tty.setraw(slaaf)
    print(os.ttyname(slaaf), flush=True)
    buf = b""
    while True:
        buf += os.read(meester, 256)
        while b"\xfd" in buf:
            frame, buf = buf.split(b"\xfd", 1)
            i = frame.find(b"\xfe\xfe")
            if i < 0 or len(frame) < i + 5:
                continue
            frame = frame[i:] + b"\xfd"
            os.write(meester, frame)                                   # echo, zoals via USB
            van, cmd, data = frame[3], frame[4], frame[5:-1]
            uit = antwoord(cmd, data)
            if LOG:
                LOG.write(f"{cmd:02x} {data.hex()} -> {uit.hex()} {stand}\n")
                LOG.flush()
            os.write(meester, bytes([0xFE, 0xFE, van, ADRES]) + uit + b"\xfd")


if __name__ == "__main__":
    main()
