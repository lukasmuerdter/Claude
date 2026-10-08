# ICD-10-GM-Assistent

Ein Agent auf Basis von Claude: Du gibst Diagnosen und/oder eine Anamnese als Freitext ein und bekommst passende **ICD-10-GM-Codes** vorgeschlagen, jeweils mit Diagnosesicherheit (G/V/Z/A), Seitenlokalisation und einer kurzen Begründung. Fehlt Information für einen genaueren Code, stellt er Rückfragen.

**So funktioniert es:** Claude durchsucht über zwei Tools (`icd_suchen`, `icd_code_pruefen`) den lokalen amtlichen ICD-10-GM-Katalog. Danach prüft das Programm selbst noch einmal jeden vorgeschlagenen Code gegen den Katalog. Die Prüfung macht der Code, nicht das Modell. Codes, die es nicht gibt oder die nicht endstellig sind, werden markiert.

> ⚠️ Das Tool ist eine Kodierhilfe und ersetzt keine ärztliche Prüfung. Gib keine Namen, Geburtsdaten oder andere identifizierende Patientendaten ein. Der Text wird an die Claude-API übermittelt. Für echte Patientendaten muss der Datenschutz (DSGVO, Auftragsverarbeitung) geklärt sein.

## Einrichtung

1. **Python-Paket installieren:** `pip install -r requirements.txt`
2. **API-Key:** Lege auf <https://console.anthropic.com> einen Key an und setze ihn als Umgebungsvariable `ANTHROPIC_API_KEY`. In Claude Code (Web) geht das über die Umgebungseinstellungen.
3. **ICD-10-GM-Katalog:** Siehe [`data/README.md`](data/README.md). Ohne Katalog läuft der Agent auch, die Codes sind dann aber **ungeprüft**.

## Benutzen

**Weboberfläche:**

```bash
python -m icd_agent.web        # → http://localhost:8000
```

**Kommandozeile:**

```bash
python -m icd_agent "DM Typ 2 mit diabetischer Nephropathie, art. Hypertonie, Z. n. Knie-TEP re."
python -m icd_agent            # interaktiv
```

**Tests** (ohne API-Zugriff):

```bash
pip install pytest && python -m pytest tests
```

## Aufbau

| Datei | Inhalt |
|---|---|
| `icd_agent/catalog.py` | Katalog laden (BfArM-Format oder `CODE;Titel`), Suche, Prüfung |
| `icd_agent/agent.py` | Agenten-Schleife mit Claude, Tools, JSON-Ergebnisschema, Code-Prüfung |
| `icd_agent/__main__.py` | Kommandozeile |
| `icd_agent/web.py`, `icd_agent/static/index.html` | Weboberfläche (nur Python-Standardbibliothek) |
