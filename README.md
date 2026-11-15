# PDF-henter for kommunale nettsider

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
