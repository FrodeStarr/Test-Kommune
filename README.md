# Henting av møtedokumenter fra kommunale nettsider

## Brønnøy kommune: kommunestyret, formannskapet og andre utvalg (`bronnoy_moter.py`)

Henter møteinnkalling, møteprotokoll og (valgfritt) saksframlegg med vedlegg
fra Brønnøy kommunes innsynsløsning
([Elements Publikum](https://prod01.elementscloud.no/publikum/964983291_PROD-964983291/Dmb)),
filtrert på utvalg, år og måned.

### Enklest: dobbeltklikk (Windows)

1. Installer Python fra <https://www.python.org/downloads/> (huk av for **«Add Python to PATH»**).
2. Last ned repoet (grønn **Code**-knapp → **Download ZIP**) og pakk ut.
3. Dobbeltklikk på **`Hent_motedokumenter.bat`** og svar på spørsmålene
   (utvalg, år, måned, hva som skal hentes). Nødvendige pakker installeres automatisk første gang.

### Fra kommandolinjen

```bash
pip install -r requirements.txt

# Kommunestyret + formannskapet, juni 2025 (innkalling og protokoll)
python bronnoy_moter.py --aar 2025 --maaned juni

# Hele 2025 for formannskapet, med saksframlegg og vedlegg for hver sak
python bronnoy_moter.py -u formannskapet --aar 2025 --med-saker

# Periode over flere måneder/år
python bronnoy_moter.py --fra 2024-09 --til 2025-03

# Bare protokoller, eller bare se hvilke møter som finnes
python bronnoy_moter.py --aar 2025 --kun-protokoll
python bronnoy_moter.py --aar 2026 --kun-liste

# Hvilke utvalg finnes?
python bronnoy_moter.py --liste-utvalg
```

| Valg | Betydning |
|---|---|
| `-u`, `--utvalg` | Ett eller flere utvalg (deler av navnet holder), eller `alle`. Standard: `kommunestyret formannskapet` |
| `-a`, `--aar` | År. Standard: inneværende år |
| `-m`, `--maaned` | Måned: `1`–`12` eller navn (`juni`, `okt`) |
| `--fra` / `--til` | Periode, `ÅÅÅÅ-MM` (til og med) |
| `--med-saker` | Last også ned saksframlegg og vedlegg for hver sak |
| `--kun-protokoll` / `--kun-innkalling` | Bare én dokumenttype |
| `--kun-liste` | Vis møtene med lenker, ikke last ned |
| `-o`, `--ut` | Mappe for nedlastinger. Standard `bronnoy_moter` |

Filene legges slik:

```
bronnoy_moter/
  Kommunestyret/
    2025-06-18 Kommunestyret/
      2025-06-18 Møteinnkalling.pdf
      2025-06-18 Møteprotokoll.pdf
      saker/
        PS 45-2025 <sakstittel>/
          00 Saksframlegg - <tittel>.pdf
          01 Vedlegg - <tittel>.pdf
  oversikt.csv
```

Filer som allerede er lastet ned, hoppes over, så programmet kan trygt kjøres
på nytt (f.eks. for å hente protokollen når den blir publisert).
Merk at en samlet møteinnkalling kan være stor (10–50 MB).

---

## Generell PDF-henter for alle nettsider (`pdf_henter.py`)

Et Python-program som starter på en nettside, følger lenker på samme nettsted
og laster ned alle PDF-filer det finner. Det lager også `oversikt.csv` med en
liste over hver PDF (URL, lenketekst, hvilken side den ble funnet på, og status).

## Installasjon

```bash
pip install -r requirements.txt
```

## Bruk

```bash
# Last ned PDF-er fra startsiden og sidene den lenker til (dybde 1)
python pdf_henter.py https://www.kommune.no/politikk/

# Gå dypere, og ta bare PDF-er som handler om budsjett eller økonomiplan
python pdf_henter.py https://www.kommune.no --dybde 2 -f budsjett -f økonomiplan

# Bare list opp PDF-ene uten å laste dem ned
python pdf_henter.py https://www.kommune.no/planer/ --kun-liste

# Lagre i egen mappe, hold deg under startsidens sti
python pdf_henter.py https://www.kommune.no/planer/ -u planer --under-sti
```

| Valg | Betydning |
|---|---|
| `-d`, `--dybde` | Hvor mange lenkenivåer som følges (0 = kun startsiden). Standard 1 |
| `-m`, `--maks-sider` | Maks antall sider som besøkes. Standard 200 |
| `-f`, `--filter` | Kun PDF-er der URL/lenketekst inneholder ordet (kan gjentas) |
| `-u`, `--ut` | Mappe for nedlastinger. Standard `pdf_nedlastinger` |
| `-p`, `--pause` | Sekunder mellom forespørsler. Standard 0.5 |
| `--kun-liste` | Bare finn PDF-er, ikke last ned |
| `--under-sti` | Følg bare sider under startsidens sti |
| `--underdomener` | Følg også underdomener (f.eks. `innsyn.kommune.no`) |
| `--alle-domener` | Ta med PDF-er som ligger på andre domener |
| `--ignorer-robots` | Ignorer `robots.txt` |

Programmet respekterer `robots.txt`, venter litt mellom forespørsler, hopper
over filer som allerede er lastet ned og sjekker at filene faktisk er PDF-er.

## Begrensninger

* Sider som bygger lenkene med JavaScript (enkelte innsyns-/postlisteløsninger)
  vil ikke bli fulgt, siden programmet leser ren HTML.
* Dokumenter bak innlogging kan ikke hentes.
