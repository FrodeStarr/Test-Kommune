#!/usr/bin/env python3
"""
bronnoy_moter.py - Laster ned møtedokumenter (PDF) for Brønnøy kommunes
politiske utvalg fra kommunens innsynsløsning (Sikri Elements Publikum).

Velg utvalg (f.eks. kommunestyret, formannskapet) og periode (år/måned).

Eksempler:
    # Innkalling + protokoll for kommunestyret og formannskapet i juni 2025
    python bronnoy_moter.py --aar 2025 --maaned 6

    # Hele 2025 for formannskapet, inkludert saksframlegg og vedlegg per sak
    python bronnoy_moter.py -u formannskapet --aar 2025 --med-saker

    # Periode på tvers av år
    python bronnoy_moter.py --fra 2024-09 --til 2025-03

    # Bare se hvilke møter som finnes
    python bronnoy_moter.py --aar 2026 --kun-liste
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

import requests

BASE = "https://prod01.elementscloud.no/publikum"
TENANT = "964983291_PROD-964983291"  # Brønnøy kommune (org.nr. 964 983 291)
MOTE_URL = f"{BASE}/{TENANT}/DmbMeeting/{{id}}"
USER_AGENT = "BronnoyMoteHenter/1.0 (+https://github.com/FrodeStarr/Test-Kommune)"

MAANEDER = ["januar", "februar", "mars", "april", "mai", "juni", "juli",
            "august", "september", "oktober", "november", "desember"]


# --------------------------------------------------------------------------- #
# Hjelpefunksjoner
# --------------------------------------------------------------------------- #
def trygt_navn(tekst: str, maks: int = 120) -> str:
    tekst = re.sub(r'[\\/:*?"<>|\r\n\t]+', "-", tekst or "").strip(" .-")
    tekst = re.sub(r"\s+", " ", tekst)
    return tekst[:maks].rstrip(" .-") or "dokument"


def parse_maaned(verdi: str) -> tuple[int, int]:
    """'2025-06' / '2025-6' / '06.2025' -> (2025, 6)"""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", verdi) or re.fullmatch(r"(\d{1,2})[./](\d{4})", verdi)
    if not m:
        raise argparse.ArgumentTypeError(f"Ugyldig måned '{verdi}', bruk ÅÅÅÅ-MM")
    a, b = m.groups()
    aar, mnd = (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
    if not 1 <= mnd <= 12:
        raise argparse.ArgumentTypeError(f"Ugyldig måned '{verdi}'")
    return aar, mnd


def parse_maaned_navn(verdi: str) -> int:
    v = verdi.strip().lower()
    if v.isdigit() and 1 <= int(v) <= 12:
        return int(v)
    for i, navn in enumerate(MAANEDER, 1):
        if navn.startswith(v[:3]) and len(v) >= 3:
            return i
    raise argparse.ArgumentTypeError(f"Ugyldig måned '{verdi}' (bruk 1-12 eller f.eks. 'juni')")


def dato(s: str) -> datetime:
    return datetime.fromisoformat(s[:19])


# --------------------------------------------------------------------------- #
# API-klient
# --------------------------------------------------------------------------- #
class Elements:
    def __init__(self, pause: float, timeout: float):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": USER_AGENT,
            "tenant": TENANT,
            "Accept": "application/json",
        })
        self.pause = pause
        self.timeout = timeout

    def _get(self, sti: str, **params):
        r = self.s.get(f"{BASE}/api/{sti}", params=params or None, timeout=self.timeout)
        r.raise_for_status()
        if self.pause:
            time.sleep(self.pause)
        return r.json()

    def moter(self, aar: int) -> list[dict]:
        return self._get("PredefinedQuery/DmbMeetings", year=aar) or []

    def mote(self, mote_id: int) -> dict:
        return self._get(f"Meetings/{mote_id}")

    def saker(self, mote_id: int) -> list[dict]:
        return self._get(f"DmbHandlings/GetByMeetingId/{mote_id}") or []

    def sak(self, sak_id: int) -> dict:
        return self._get(f"DmbHandlings/{sak_id}")

    def last_ned(self, url: str, maal: Path) -> tuple[str, int]:
        """Laster ned til maal (filendelse settes ut fra serveren). Returnerer (status, bytes)."""
        with self.s.get(url, timeout=self.timeout, stream=True,
                        headers={"Accept": "*/*"}) as r:
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "").lower()
            endelse = ".pdf"
            cd = r.headers.get("Content-Disposition", "")
            m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd, re.IGNORECASE)
            if m:
                ext = Path(unquote(m.group(1)).strip()).suffix.lower()
                if ext:
                    endelse = ext
            elif "pdf" not in ctype:
                endelse = ".bin"
            maal = maal.with_suffix(endelse)
            if maal.exists() and maal.stat().st_size > 0:
                return f"fantes allerede: {maal.name}", 0
            maal.parent.mkdir(parents=True, exist_ok=True)
            tmp = maal.with_suffix(maal.suffix + ".part")
            n = 0
            with tmp.open("wb") as f:
                for bit in r.iter_content(1 << 16):
                    f.write(bit)
                    n += len(bit)
            tmp.replace(maal)
        if self.pause:
            time.sleep(self.pause)
        return f"lastet ned: {maal.name}", n


# --------------------------------------------------------------------------- #
# Programlogikk
# --------------------------------------------------------------------------- #
def finn_periode(args) -> tuple[date, date]:
    """Returnerer [fra, til) som datoer."""
    if args.fra or args.til:
        fa, fm = args.fra or (args.til[0], 1)
        ta, tm = args.til or (date.today().year, date.today().month)
    else:
        aar = args.aar or date.today().year
        if args.maaned:
            fa, fm, ta, tm = aar, args.maaned, aar, args.maaned
        else:
            fa, fm, ta, tm = aar, 1, aar, 12
    start = date(fa, fm, 1)
    slutt = date(ta + (tm == 12), tm % 12 + 1, 1)
    if slutt <= start:
        sys.exit("Feil: 'til' må være etter 'fra'.")
    return start, slutt


def velg_utvalg(alle: list[dict], onsket: list[str]) -> list[dict]:
    if any(o.lower() == "alle" for o in onsket):
        return alle
    ut = []
    for m in alle:
        navn = m["UT_NAVN"].lower()
        if any(o.lower() in navn for o in onsket):
            ut.append(m)
    return ut


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Last ned møtedokumenter (PDF) for Brønnøy kommunes politiske utvalg.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("-u", "--utvalg", nargs="+", default=["kommunestyret", "formannskapet"],
                   help="Utvalg (hele eller deler av navnet), eller 'alle'")
    p.add_argument("-a", "--aar", type=int, help="År (standard: inneværende år)")
    p.add_argument("-m", "--maaned", type=parse_maaned_navn,
                   help="Måned i året: 1-12 eller navn, f.eks. 'juni'")
    p.add_argument("--fra", type=parse_maaned, help="Fra og med måned, ÅÅÅÅ-MM")
    p.add_argument("--til", type=parse_maaned, help="Til og med måned, ÅÅÅÅ-MM")
    p.add_argument("--med-saker", action="store_true",
                   help="Last også ned saksframlegg og vedlegg for hver sak")
    p.add_argument("--kun-protokoll", action="store_true", help="Bare møteprotokoller")
    p.add_argument("--kun-innkalling", action="store_true", help="Bare møteinnkallinger")
    p.add_argument("--kun-liste", action="store_true", help="Bare vis møtene, ikke last ned")
    p.add_argument("--liste-utvalg", action="store_true", help="Vis hvilke utvalg som finnes")
    p.add_argument("-o", "--ut", default="bronnoy_moter", help="Mappe for nedlastinger")
    p.add_argument("-p", "--pause", type=float, default=0.3, help="Pause (sek) mellom kall")
    p.add_argument("-t", "--timeout", type=float, default=120, help="Timeout per kall (sek)")
    args = p.parse_args(argv)

    api = Elements(args.pause, args.timeout)
    start, slutt = finn_periode(args)

    # Hent møter for alle år i perioden
    moter: list[dict] = []
    try:
        for aar in range(start.year, (slutt.year if slutt.month > 1 else slutt.year - 1) + 1):
            moter += api.moter(aar)
    except requests.RequestException as e:
        sys.exit(f"Klarte ikke å hente møteliste: {e}")

    if args.liste_utvalg:
        for navn in sorted({m["UT_NAVN"] for m in moter}):
            print(" -", navn)
        return 0

    moter = [m for m in velg_utvalg(moter, args.utvalg)
             if start <= dato(m["MO_START"]).date() < slutt]
    moter.sort(key=lambda m: m["MO_START"])

    periode = f"{start:%m.%Y} – {date.fromordinal(slutt.toordinal() - 1):%m.%Y}"
    print(f"Fant {len(moter)} møter ({', '.join(args.utvalg)}) i perioden {periode}.")
    if not moter:
        print("Tips: bruk --liste-utvalg for å se gyldige utvalgsnavn.")
        return 1

    if args.kun_liste:
        for m in moter:
            d = dato(m["MO_START"])
            print(f"  {d:%d.%m.%Y %H:%M}  {m['UT_NAVN']:<40} {MOTE_URL.format(id=m['MO_ID'])}")
        return 0

    ut = Path(args.ut)
    logg: list[dict] = []
    totalt = 0

    def hent(url: str, maal: Path, info: dict) -> None:
        nonlocal totalt
        try:
            status, n = api.last_ned(url, maal)
            totalt += n
        except requests.RequestException as e:
            status = f"feil: {e}"
        print(f"      {status}" + (f" ({n // 1024} kB)" if status.startswith("lastet") else ""))
        logg.append({**info, "url": url, "status": status})

    for m in moter:
        d = dato(m["MO_START"])
        mappe = ut / m["UT_NAVN"] / f"{d:%Y-%m-%d} {trygt_navn(m['UT_NAVN'])}"
        print(f"\n{d:%d.%m.%Y}  {m['UT_NAVN']}  ({MOTE_URL.format(id=m['MO_ID'])})")
        felles = {"utvalg": m["UT_NAVN"], "dato": f"{d:%Y-%m-%d}", "mote_id": m["MO_ID"]}

        try:
            detaljer = api.mote(m["MO_ID"])
        except requests.RequestException as e:
            print(f"   ! Klarte ikke å hente møtet: {e}")
            continue
        db = detaljer.get("Database") or m.get("Database")

        for dok in detaljer.get("MeetingDocuments") or []:
            typ = dok.get("DmbDocumentTypeId")
            if dok.get("IsRestricted"):
                continue
            if args.kun_protokoll and typ != "MP":
                continue
            if args.kun_innkalling and typ != "MI":
                continue
            tittel = (dok.get("Title") or typ).strip()
            print(f"   {tittel}")
            url = f"{BASE}/Documents/ShowMeetingDocument/{db}/{m['MO_ID']}/{typ}/{dok['Id']}"
            hent(url, mappe / f"{d:%Y-%m-%d} {trygt_navn(tittel)}.pdf",
                 {**felles, "sak": "", "dokument": tittel})

        if not args.med_saker or args.kun_protokoll or args.kun_innkalling:
            continue

        try:
            saker = api.saker(m["MO_ID"])
        except requests.RequestException as e:
            print(f"   ! Klarte ikke å hente sakskart: {e}")
            continue
        for s in sorted(saker, key=lambda s: s.get("SequenceNumber") or 0):
            saksnr = f"{s.get('MeetingCaseTypeId', 'PS')} {s.get('SequenceNumber')}-{s.get('Year')}"
            sakstittel = f"{saksnr} {s.get('Title') or ''}"
            try:
                full = api.sak(s["Id"])
            except requests.RequestException as e:
                print(f"   ! {saksnr}: {e}")
                continue
            reg = full.get("RegistryEntry") or {}
            doks = [x for x in reg.get("Documents") or []
                    if (x.get("DocumentDescription") or {}).get("IsPublished")]
            if not doks:
                continue
            print(f"   {sakstittel[:90]}")
            sakmappe = mappe / "saker" / trygt_navn(sakstittel, 100)
            nr = 0
            for x in doks:
                dd = x["DocumentDescription"]
                tittel = dd.get("DocumentTitle") or "dokument"
                # Fjern filendelse fra tittelen (f.eks. "Notat.docx" -> "Notat")
                tittel = re.sub(r"\.(pdf|docx?|xlsx?|pptx?|odt|txt|msg|jpe?g|png)$", "", tittel.strip(),
                                flags=re.IGNORECASE)
                if x.get("IsMainDocument"):
                    url = f"{BASE}/Documents/ShowDmbHandlingDocument/{db}/{s['Id']}/CasesFremlegg"
                    filnavn = f"00 Saksframlegg - {trygt_navn(tittel, 90)}"
                else:
                    url = f"{BASE}/Documents/ShowDocument/{reg.get('Database') or db}/{reg['Id']}/{dd['Id']}"
                    nr += 1
                    filnavn = f"{nr:02d} Vedlegg - {trygt_navn(tittel, 90)}"
                hent(url, sakmappe / f"{filnavn}.pdf", {**felles, "sak": sakstittel, "dokument": tittel})

    ut.mkdir(parents=True, exist_ok=True)
    rapport = ut / "oversikt.csv"
    ny = not rapport.exists()
    with rapport.open("a", newline="", encoding="utf-8-sig" if ny else "utf-8") as f:
        w = csv.DictWriter(f, delimiter=";",
                           fieldnames=["utvalg", "dato", "mote_id", "sak", "dokument", "status", "url"])
        if ny:
            w.writeheader()
        w.writerows(logg)

    nye = sum(1 for r in logg if r["status"].startswith("lastet"))
    feil = sum(1 for r in logg if r["status"].startswith("feil"))
    print(f"\nFerdig: {nye} nye filer ({totalt / 1e6:.1f} MB), {feil} feil. "
          f"Lagret i {ut.resolve()}\nOversikt: {rapport}")
    return 0 if not feil else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit("\nAvbrutt.")
