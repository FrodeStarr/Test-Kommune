#!/usr/bin/env python3
"""
pdf_henter.py - Henter PDF-filer fra en (kommunal) nettside.

Programmet starter på en gitt URL, følger lenker innenfor samme domene
(ned til en valgt dybde), finner alle lenker til PDF-filer og laster dem ned.

Eksempler:
    python pdf_henter.py https://www.oslo.kommune.no/politikk/
    python pdf_henter.py https://www.bergen.kommune.no --dybde 2 --filter budsjett
    python pdf_henter.py https://www.trondheim.kommune.no --kun-liste
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "KommunePdfHenter/1.0 (+https://github.com/FrodeStarr/Test-Kommune)"
HTML_TYPER = ("text/html", "application/xhtml+xml")
IKKE_SIDER = re.compile(
    r"\.(jpe?g|png|gif|svg|webp|ico|css|js|zip|docx?|xlsx?|pptx?|mp4|mp3|xml|json)$",
    re.IGNORECASE,
)


def normaliser(url: str) -> str:
    """Fjerner #fragment og trailing whitespace."""
    return urldefrag(url.strip())[0]


def ser_ut_som_pdf(url: str) -> bool:
    sti = urlparse(url).path.lower()
    return sti.endswith(".pdf") or "/pdf/" in sti or "format=pdf" in url.lower()


def samme_domene(url: str, basis_vert: str, tillat_underdomener: bool) -> bool:
    vert = (urlparse(url).hostname or "").lower()
    if vert == basis_vert:
        return True
    if tillat_underdomener:
        rot = basis_vert.removeprefix("www.")
        return vert == rot or vert.endswith("." + rot)
    return False


def trygt_filnavn(url: str, respons: requests.Response | None = None) -> str:
    navn = ""
    if respons is not None:
        cd = respons.headers.get("Content-Disposition", "")
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd, re.IGNORECASE)
        if m:
            navn = unquote(m.group(1))
    if not navn:
        navn = unquote(Path(urlparse(url).path).name) or "dokument"
    navn = re.sub(r"[^\w.\-æøåÆØÅ ]", "_", navn).strip(" .") or "dokument"
    if not navn.lower().endswith(".pdf"):
        navn += ".pdf"
    return navn[:150]


class PdfHenter:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.start = normaliser(args.url)
        self.basis_vert = (urlparse(self.start).hostname or "").lower()
        self.ut = Path(args.ut)
        self.okt = requests.Session()
        self.okt.headers["User-Agent"] = USER_AGENT
        self.robots = self._last_robots()
        self.besokt: set[str] = set()
        self.pdf_lenker: dict[str, dict] = {}  # url -> info
        self.filter = [f.lower() for f in (args.filter or [])]

    # ---------- hjelpere ----------
    def _last_robots(self) -> RobotFileParser | None:
        if self.args.ignorer_robots:
            return None
        p = urlparse(self.start)
        rp = RobotFileParser()
        try:
            r = self.okt.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=self.args.timeout)
            rp.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            rp.parse([])
        return rp

    def _tillatt(self, url: str) -> bool:
        return self.robots is None or self.robots.can_fetch(USER_AGENT, url)

    def _pause(self) -> None:
        if self.args.pause > 0:
            time.sleep(self.args.pause)

    def _matcher_filter(self, *tekster: str) -> bool:
        if not self.filter:
            return True
        samlet = " ".join(tekster).lower()
        return any(f in samlet for f in self.filter)

    def logg(self, melding: str) -> None:
        if not self.args.stille:
            print(melding, flush=True)

    # ---------- crawling ----------
    def kryp(self) -> None:
        ko: deque[tuple[str, int]] = deque([(self.start, 0)])
        while ko:
            if self.args.maks_sider and len(self.besokt) >= self.args.maks_sider:
                self.logg(f"Nådde maks antall sider ({self.args.maks_sider}).")
                break
            url, dybde = ko.popleft()
            if url in self.besokt or not self._tillatt(url):
                continue
            self.besokt.add(url)

            try:
                r = self.okt.get(url, timeout=self.args.timeout)
            except requests.RequestException as e:
                self.logg(f"  ! Feil ved henting av {url}: {e}")
                continue
            self._pause()

            ctype = r.headers.get("Content-Type", "").lower()
            if "application/pdf" in ctype:
                # Lenken pekte direkte på en PDF uten .pdf-endelse
                self._registrer_pdf(r.url, "", url)
                continue
            if not r.ok or not ctype.startswith(HTML_TYPER):
                continue

            self.logg(f"[{len(self.besokt)}] dybde {dybde}: {url}")
            suppe = BeautifulSoup(r.content, "html.parser")  # lar bs4 finne tegnsett

            for a in suppe.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith(("mailto:", "tel:", "javascript:")):
                    continue
                lenke = normaliser(urljoin(r.url, href))
                if not lenke.startswith(("http://", "https://")):
                    continue
                tekst = a.get_text(" ", strip=True)

                if ser_ut_som_pdf(lenke):
                    if self.args.alle_domener or samme_domene(
                        lenke, self.basis_vert, True
                    ):
                        self._registrer_pdf(lenke, tekst, url)
                elif (
                    dybde < self.args.dybde
                    and lenke not in self.besokt
                    and samme_domene(lenke, self.basis_vert, self.args.underdomener)
                    and not IKKE_SIDER.search(urlparse(lenke).path)
                    and (not self.args.under_sti or urlparse(lenke).path.startswith(
                        urlparse(self.start).path))
                ):
                    ko.append((lenke, dybde + 1))

    def _registrer_pdf(self, url: str, tekst: str, side: str) -> None:
        if url in self.pdf_lenker:
            return
        if not self._matcher_filter(url, tekst):
            return
        self.pdf_lenker[url] = {"url": url, "lenketekst": tekst, "funnet_paa": side}
        self.logg(f"    PDF: {tekst or url}")

    # ---------- nedlasting ----------
    def last_ned(self) -> None:
        self.ut.mkdir(parents=True, exist_ok=True)
        brukte_navn: set[str] = {p.name for p in self.ut.glob("*.pdf")}
        for i, info in enumerate(self.pdf_lenker.values(), 1):
            url = info["url"]
            if not self._tillatt(url):
                info["status"] = "blokkert av robots.txt"
                continue
            try:
                with self.okt.get(url, timeout=self.args.timeout, stream=True) as r:
                    r.raise_for_status()
                    ctype = r.headers.get("Content-Type", "").lower()
                    data = r.content
                if not data.startswith(b"%PDF") and "pdf" not in ctype:
                    info["status"] = f"ikke PDF ({ctype or 'ukjent type'})"
                    continue

                navn = trygt_filnavn(url, r)
                maal = self.ut / navn
                if maal.exists():
                    if maal.read_bytes() == data:
                        info.update(status="fantes allerede", fil=str(maal))
                        self.logg(f"  [{i}/{len(self.pdf_lenker)}] = {navn} (finnes)")
                        continue
                    stamme, n = maal.stem, 2
                    while (self.ut / f"{stamme}_{n}.pdf").name in brukte_navn:
                        n += 1
                    maal = self.ut / f"{stamme}_{n}.pdf"
                maal.write_bytes(data)
                brukte_navn.add(maal.name)
                info.update(status="lastet ned", fil=str(maal), bytes=len(data))
                self.logg(f"  [{i}/{len(self.pdf_lenker)}] ↓ {maal.name} ({len(data)//1024} kB)")
            except requests.RequestException as e:
                info["status"] = f"feil: {e}"
                self.logg(f"  [{i}/{len(self.pdf_lenker)}] ! {url}: {e}")
            self._pause()

    def skriv_rapport(self) -> Path:
        self.ut.mkdir(parents=True, exist_ok=True)
        fil = self.ut / "oversikt.csv"
        felt = ["url", "lenketekst", "funnet_paa", "status", "fil", "bytes"]
        with fil.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=felt, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(self.pdf_lenker.values())
        return fil


def lag_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Henter PDF-filer fra en kommunal nettside.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("url", help="Startside, f.eks. https://www.kommune.no/politikk/")
    p.add_argument("-u", "--ut", default="pdf_nedlastinger", help="Mappe for nedlastede filer")
    p.add_argument("-d", "--dybde", type=int, default=1,
                   help="Hvor mange lenkenivåer som følges fra startsiden (0 = kun startsiden)")
    p.add_argument("-m", "--maks-sider", type=int, default=200,
                   help="Maks antall HTML-sider som besøkes (0 = ubegrenset)")
    p.add_argument("-f", "--filter", action="append",
                   help="Kun PDF-er der URL eller lenketekst inneholder ordet (kan gjentas)")
    p.add_argument("-p", "--pause", type=float, default=0.5,
                   help="Sekunder pause mellom forespørsler (vær snill mot serveren)")
    p.add_argument("-t", "--timeout", type=float, default=30, help="Timeout per forespørsel")
    p.add_argument("--kun-liste", action="store_true",
                   help="Bare finn og list PDF-ene, ikke last ned")
    p.add_argument("--under-sti", action="store_true",
                   help="Følg kun sider under startsidens sti")
    p.add_argument("--underdomener", action="store_true",
                   help="Følg også lenker til underdomener (f.eks. innsyn.kommune.no)")
    p.add_argument("--alle-domener", action="store_true",
                   help="Ta med PDF-lenker som peker til andre domener")
    p.add_argument("--ignorer-robots", action="store_true", help="Ignorer robots.txt")
    p.add_argument("-s", "--stille", action="store_true", help="Mindre utskrift")
    return p


def main(argv: list[str] | None = None) -> int:
    args = lag_parser().parse_args(argv)
    if not urlparse(args.url).scheme:
        args.url = "https://" + args.url

    henter = PdfHenter(args)
    print(f"Leter etter PDF-er på {henter.start} (dybde {args.dybde}) ...")
    try:
        henter.kryp()
    except KeyboardInterrupt:
        print("\nAvbrutt under søk – fortsetter med det som er funnet.")

    print(f"\nFant {len(henter.pdf_lenker)} PDF-er på {len(henter.besokt)} sider.")
    if not henter.pdf_lenker:
        return 1

    if args.kun_liste:
        for info in henter.pdf_lenker.values():
            print(f"- {info['lenketekst'] or '(uten tekst)'}\n  {info['url']}")
    else:
        try:
            henter.last_ned()
        except KeyboardInterrupt:
            print("\nNedlasting avbrutt.")
        ok = sum(1 for i in henter.pdf_lenker.values() if i.get("status") == "lastet ned")
        print(f"\nLastet ned {ok} nye filer til {henter.ut.resolve()}")

    print(f"Oversikt lagret i {henter.skriv_rapport()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
