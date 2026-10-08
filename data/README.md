# ICD-10-GM-Katalog

Der amtliche Katalog kommt vom **BfArM**. Er ist kostenlos, der Download erfordert aber die Zustimmung zu den Nutzungsbedingungen.

1. Öffne <https://www.bfarm.de> → Kodiersysteme → Klassifikationen → ICD-10-GM → Downloads.
2. Lade die aktuelle Version herunter, und zwar **"Metadaten / Systematik"** im **ASCII/CSV-Format** (ZIP).
3. Kopiere aus dem ZIP die Datei `icd10gm<JAHR>syst_kodes.txt` (Ordner `Klassifikationsdateien`) hierher in `data/`.

Der Agent findet die Datei automatisch. Alternativ kannst du einen Pfad über die Umgebungsvariable `ICD_KATALOG` angeben.

Auch eine einfache Textdatei mit einer Zeile `CODE;Titel` pro Code funktioniert.
