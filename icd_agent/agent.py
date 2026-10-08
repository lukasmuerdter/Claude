"""Agent: schlägt zu Diagnosen/Anamnese passende ICD-10-GM-Codes vor.

Claude durchsucht den lokalen ICD-10-GM-Katalog über Tools und gibt das Ergebnis
als strukturiertes JSON zurück. Jeder vorgeschlagene Code wird danach im Code
(nicht vom Modell) gegen den Katalog geprüft.
"""

from __future__ import annotations

import json
import os
from typing import Any

import anthropic

from .catalog import IcdKatalog

MODEL = "claude-opus-5-5"
MAX_RUNDEN = 15

SYSTEM_MIT_KATALOG = """Du unterstützt Ärztinnen und Ärzte in Deutschland bei der Kodierung nach ICD-10-GM.
Du bekommst Diagnosen und/oder eine Anamnese als Freitext und schlägst passende Schlüsselnummern vor.

Arbeitsweise:
- Suche jeden Code mit dem Tool `icd_suchen` und prüfe ihn mit `icd_code_pruefen`, bevor du ihn vorschlägst. Schlage nur Codes vor, die im Katalog existieren.
- Kodiere so spezifisch wie es die Angaben erlauben, bevorzugt endstellige Codes. Fehlt Information für einen spezifischeren Code (z. B. Typ, Seite, Komplikation, Akuität), nimm den passenden Restcode und nenne die fehlende Angabe unter `rueckfragen`.
- Beachte Kreuz-Stern-System und Ausrufezeichen-Codes, wenn zutreffend.
- Diagnosesicherheit: G = gesichert, V = Verdacht, Z = Zustand nach, A = ausgeschlossen – so wie es aus dem Text hervorgeht.
- Kodiere nur, was im Text steht oder eindeutig daraus folgt. Erfinde keine Diagnosen; reine Symptome nur, wenn keine Diagnose dazu genannt ist.
- Schreibe Begründungen kurz und auf Deutsch."""

SYSTEM_OHNE_KATALOG = (
    SYSTEM_MIT_KATALOG.split("Arbeitsweise:")[0]
    + """Arbeitsweise:
- Es ist kein Katalog geladen. Schlage Codes aus deinem Wissen über die ICD-10-GM vor; sie werden als ungeprüft markiert.
- Kodiere so spezifisch wie es die Angaben erlauben. Fehlende Angaben für einen spezifischeren Code nennst du unter `rueckfragen`.
- Diagnosesicherheit: G = gesichert, V = Verdacht, Z = Zustand nach, A = ausgeschlossen.
- Kodiere nur, was im Text steht oder eindeutig daraus folgt. Schreibe Begründungen kurz und auf Deutsch."""
)

TOOLS = [
    {
        "name": "icd_suchen",
        "description": (
            "Volltextsuche im ICD-10-GM-Katalog. Liefert bis zu 25 Treffer mit Code, Titel "
            "und ob der Code endstellig ist. Akzeptiert deutsche Begriffe (z. B. 'Hypertonie', "
            "'Diabetes Typ 2 Nephropathie') oder einen Code-Anfang (z. B. 'E11')."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"suchbegriff": {"type": "string"}},
            "required": ["suchbegriff"],
            "additionalProperties": False,
        },
    },
    {
        "name": "icd_code_pruefen",
        "description": (
            "Prüft, ob ein Code im ICD-10-GM-Katalog existiert. Liefert Titel, ob er endstellig ist, "
            "und bei nicht endstelligen Codes die Unterkodes."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
    },
]

ERGEBNIS_SCHEMA = {
    "type": "object",
    "properties": {
        "codes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "titel": {"type": "string"},
                    "diagnosesicherheit": {"type": "string", "enum": ["G", "V", "Z", "A"]},
                    "seitenlokalisation": {"type": "string", "enum": ["R", "L", "B", "keine"]},
                    "begruendung": {"type": "string"},
                },
                "required": ["code", "titel", "diagnosesicherheit", "seitenlokalisation", "begruendung"],
                "additionalProperties": False,
            },
        },
        "rueckfragen": {"type": "array", "items": {"type": "string"}},
        "hinweise": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["codes", "rueckfragen", "hinweise"],
    "additionalProperties": False,
}


class KodierFehler(RuntimeError):
    pass


def _tool_ausfuehren(katalog: IcdKatalog, name: str, eingabe: dict[str, Any]) -> str:
    if name == "icd_suchen":
        treffer = katalog.suchen(str(eingabe.get("suchbegriff", "")))
        if not treffer:
            return "Keine Treffer. Versuche einen anderen oder allgemeineren Begriff."
        return "\n".join(
            f"{e.code} | {e.titel} | {'endstellig' if e.endstellig else 'nicht endstellig'}" for e in treffer
        )
    if name == "icd_code_pruefen":
        eintrag = katalog.pruefen(str(eingabe.get("code", "")))
        if eintrag is None:
            return "Code existiert nicht im Katalog."
        text = f"{eintrag.code} | {eintrag.titel} | {'endstellig' if eintrag.endstellig else 'nicht endstellig'}"
        if not eintrag.endstellig:
            text += "\nUnterkodes:\n" + "\n".join(f"{u.code} | {u.titel}" for u in katalog.unterkodes(eintrag.code))
        return text
    raise KodierFehler(f"Unbekanntes Tool: {name}")


def _pruefen(ergebnis: dict[str, Any], katalog: IcdKatalog | None) -> dict[str, Any]:
    """Setzt pro Code die Felder `im_katalog`, `endstellig` und ggf. den amtlichen Titel."""
    for c in ergebnis["codes"]:
        eintrag = katalog.pruefen(c["code"]) if katalog else None
        c["im_katalog"] = None if katalog is None else eintrag is not None
        c["endstellig"] = eintrag.endstellig if eintrag else None
        if eintrag:
            c["code"] = eintrag.code
            c["titel"] = eintrag.titel
    return ergebnis


def kodieren(text: str, katalog: IcdKatalog | None, client: anthropic.Anthropic | None = None) -> dict[str, Any]:
    """Gibt {codes, rueckfragen, hinweise, katalog} für den Freitext zurück."""
    if not text.strip():
        raise KodierFehler("Bitte Diagnosen oder Anamnese eingeben.")
    if client is None:
        if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            raise KodierFehler("Kein ANTHROPIC_API_KEY gesetzt (siehe README).")
        client = anthropic.Anthropic()

    messages: list[dict[str, Any]] = [{"role": "user", "content": text}]
    extra: dict[str, Any] = {"tools": TOOLS} if katalog else {}

    for _ in range(MAX_RUNDEN):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_MIT_KATALOG if katalog else SYSTEM_OHNE_KATALOG,
            messages=messages,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": ERGEBNIS_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            **extra,
        )

        if response.stop_reason == "refusal":
            raise KodierFehler("Die Anfrage wurde vom Modell abgelehnt. Bitte Text umformulieren.")
        if response.stop_reason == "max_tokens":
            raise KodierFehler("Antwort zu lang – bitte weniger Text auf einmal eingeben.")

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            ergebnisse = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    inhalt = _tool_ausfuehren(katalog, block.name, block.input)
                    ergebnisse.append({"type": "tool_result", "tool_use_id": block.id, "content": inhalt})
                except KodierFehler as e:
                    ergebnisse.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": str(e), "is_error": True}
                    )
            messages.append({"role": "user", "content": ergebnisse})
            continue

        json_text = next((b.text for b in response.content if b.type == "text"), None)
        if json_text is None:
            raise KodierFehler("Keine Antwort vom Modell erhalten.")
        ergebnis = _pruefen(json.loads(json_text), katalog)
        ergebnis["katalog"] = katalog.quelle if katalog else None
        return ergebnis

    raise KodierFehler("Zu viele Suchschritte – bitte Eingabe vereinfachen.")
