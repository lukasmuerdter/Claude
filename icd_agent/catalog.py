"""ICD-10-GM-Katalog laden und durchsuchen.

Erwartet wird die maschinenlesbare Fassung des BfArM
(Datei ``icd10gm<JAHR>syst_kodes.txt`` aus dem ZIP "ICD-10-GM <JAHR> Metadaten/
Systematik ASCII"). Alternativ reicht eine einfache Textdatei mit
``CODE;Titel`` pro Zeile.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

CODE_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?$")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class IcdEintrag:
    code: str
    titel: str
    endstellig: bool  # True = terminale (abrechenbare) Schlüsselnummer


def _normalisieren(text: str) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    return text


def _code_normalisieren(code: str) -> str:
    code = code.strip().upper().rstrip("-+*!†")
    if len(code) > 3 and "." not in code:
        code = f"{code[:3]}.{code[3:]}"
    return code


def _datei_lesen(pfad: Path) -> list[str]:
    roh = pfad.read_bytes()
    try:
        text = roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = roh.decode("cp1252")
    return text.splitlines()


class IcdKatalog:
    def __init__(self, eintraege: list[IcdEintrag], quelle: str):
        self.quelle = quelle
        self._nach_code = {e.code: e for e in eintraege}
        self._suchtext = {e.code: _normalisieren(f"{e.code} {e.titel}") for e in eintraege}

    def __len__(self) -> int:
        return len(self._nach_code)

    @classmethod
    def aus_datei(cls, pfad: Path) -> "IcdKatalog":
        zeilen = _datei_lesen(pfad)
        roh: list[tuple[str, str, bool | None]] = []
        for zeile in zeilen:
            felder = zeile.split(";")
            # BfArM-Format: 0 Ebene, 1 T/N, 2 X/S, 3 Kapitel, 4 Gruppe,
            # 5 Code mit Zeichen, 6 Code ohne Zeichen, 7 Code ohne Punkt, 8 Titel
            if len(felder) >= 9 and felder[1] in ("T", "N"):
                code = _code_normalisieren(felder[6])
                if CODE_RE.match(code):
                    roh.append((code, felder[8].strip(), felder[1] == "T"))
                continue
            if len(felder) >= 2:
                code = _code_normalisieren(felder[0])
                if CODE_RE.match(code):
                    roh.append((code, felder[1].strip(), None))

        codes = {c for c, _, _ in roh}
        eintraege = []
        for code, titel, endstellig in roh:
            if endstellig is None:  # Einfaches Format: aus der Hierarchie ableiten
                endstellig = not any(
                    c != code and c.replace(".", "").startswith(code.replace(".", ""))
                    for c in codes
                )
            eintraege.append(IcdEintrag(code, titel, endstellig))
        return cls(eintraege, quelle=pfad.name)

    def pruefen(self, code: str) -> IcdEintrag | None:
        return self._nach_code.get(_code_normalisieren(code))

    def unterkodes(self, code: str) -> list[IcdEintrag]:
        basis = _code_normalisieren(code).replace(".", "")
        return [
            e
            for c, e in self._nach_code.items()
            if c.replace(".", "").startswith(basis) and c.replace(".", "") != basis
        ]

    def suchen(self, suchbegriff: str, limit: int = 25) -> list[IcdEintrag]:
        if CODE_RE.match(_code_normalisieren(suchbegriff)) or re.match(r"^[A-Za-z]\d{1,2}$", suchbegriff.strip()):
            praefix = _code_normalisieren(suchbegriff).replace(".", "")
            treffer = [e for c, e in self._nach_code.items() if c.replace(".", "").startswith(praefix)]
            return treffer[:limit]

        woerter = [w for w in re.split(r"[^\w]+", _normalisieren(suchbegriff)) if len(w) >= 3]
        if not woerter:
            return []
        bewertet = []
        for code, text in self._suchtext.items():
            punkte = sum(1 for w in woerter if w in text)
            if punkte:
                eintrag = self._nach_code[code]
                # Bei Gleichstand: alle Wörter getroffen, dann endstellige und kürzere Titel zuerst
                bewertet.append((-punkte, not eintrag.endstellig, len(eintrag.titel), code))
        bewertet.sort()
        return [self._nach_code[code] for *_, code in bewertet[:limit]]


def katalog_finden() -> Path | None:
    """Sucht die Katalogdatei: zuerst $ICD_KATALOG, dann im Ordner data/."""
    if pfad := os.environ.get("ICD_KATALOG"):
        return Path(pfad)
    kandidaten = sorted(DATA_DIR.glob("*syst_kodes*.txt"), reverse=True)
    if not kandidaten:
        kandidaten = sorted(p for p in DATA_DIR.glob("*.txt") if p.name.lower() != "readme.txt")
    return kandidaten[0] if kandidaten else None


def katalog_laden() -> IcdKatalog | None:
    pfad = katalog_finden()
    return IcdKatalog.aus_datei(pfad) if pfad and pfad.exists() else None
