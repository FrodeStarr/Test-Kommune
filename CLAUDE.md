# Instruksjoner for Claude

Dette repoet henter møtedokumenter (PDF) fra Brønnøy kommunes innsynsløsning
(Elements Publikum) med `bronnoy_moter.py`. Brukeren skriver på norsk.

## Når brukeren ber om møtedokumenter

Eksempler: «hent kommunestyret juni 2025», «protokoller formannskapet 2025»,
«alt fra kommunestyret siste møte med saker».

1. Tolk forespørselen til argumenter for `bronnoy_moter.py`:
   - utvalg: `-u kommunestyret`, `-u formannskapet`, begge (standard) eller `-u alle`
   - periode: `--aar ÅÅÅÅ`, `--maaned 1-12|navn`, eller `--fra ÅÅÅÅ-MM --til ÅÅÅÅ-MM`
   - innhold: standard = innkalling + protokoll; `--med-saker` for saksframlegg
     og vedlegg; `--kun-protokoll` / `--kun-innkalling`
   - «siste møte»: kjør først med `--kun-liste` og velg riktig måned.
   - Er noe uklart (f.eks. år mangler), bruk inneværende år og si det.
2. Kjør med utdata i arbeidsmappen, så filene kan sendes til brukeren:
   `python3 bronnoy_moter.py <argumenter> -o bronnoy_moter`
   (installer avhengigheter med `pip install -r requirements.txt` om nødvendig).
3. Lever filene direkte i samtalen med SendUserFile (`display: "attach"`):
   - Opptil ca. 10 filer: send PDF-ene enkeltvis.
   - Flere filer: pakk dem i én ZIP per utvalg/periode
     (f.eks. `Kommunestyret_2025-06.zip`) og send ZIP-en.
4. Svar kort på norsk: hvilke møter som ble funnet, hvilke dokumenter som er
   sendt, og om noe mangler (f.eks. protokoll ikke publisert ennå).

## Viktig

- Nedlastede filer (`bronnoy_moter/`, `*.zip`) skal **aldri** committes.
- Økten må kjøre i miljøet **Test-Kommune**, som gir nettverkstilgang til
  `prod01.elementscloud.no` og `www.bronnoy.kommune.no`.
