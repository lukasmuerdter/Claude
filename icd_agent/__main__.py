"""Kommandozeile: python -m icd_agent "Diagnosen/Anamnese ..."  (ohne Text: interaktiv)"""

import sys

from .agent import KodierFehler, kodieren
from .catalog import katalog_laden


def ausgeben(ergebnis: dict) -> None:
    for c in ergebnis["codes"]:
        if c["im_katalog"] is None:
            status = "ungeprüft"
        elif not c["im_katalog"]:
            status = "NICHT IM KATALOG"
        elif not c["endstellig"]:
            status = "nicht endstellig"
        else:
            status = "ok"
        seite = f" {c['seitenlokalisation']}" if c["seitenlokalisation"] != "keine" else ""
        print(f"  {c['code']:<8} {c['diagnosesicherheit']}{seite:<3} {c['titel']}  [{status}]")
        print(f"           → {c['begruendung']}")
    for frage in ergebnis["rueckfragen"]:
        print(f"  ? {frage}")
    for hinweis in ergebnis["hinweise"]:
        print(f"  ! {hinweis}")


def main() -> None:
    katalog = katalog_laden()
    if katalog:
        print(f"Katalog: {katalog.quelle} ({len(katalog)} Codes)")
    else:
        print("Kein ICD-10-GM-Katalog in data/ gefunden – Codes werden NICHT geprüft (siehe data/README.md).")

    texte = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else None
    while True:
        text = texte.pop() if texte else input("\nDiagnosen/Anamnese (leer = Ende): ").strip()
        if not text:
            break
        try:
            ausgeben(kodieren(text, katalog))
        except KodierFehler as e:
            print(f"Fehler: {e}")
        if texte is not None:
            break


if __name__ == "__main__":
    main()
