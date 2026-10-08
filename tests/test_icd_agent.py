"""Tests ohne API-Zugriff: Katalog-Parser, Suche und Agenten-Schleife mit Fake-Client.

Die Katalogzeilen hier sind nur Testdaten, kein echter Katalog.
"""

import json
from pathlib import Path
from types import SimpleNamespace

from icd_agent.agent import kodieren
from icd_agent.catalog import IcdKatalog

BFARM_ZEILEN = """\
3;N;X;04;E10;E11.-;E11;E11;Diabetes mellitus, Typ 2;Diabetes mellitus, Typ 2;;;P;P;
4;N;S;04;E10;E11.9-;E11.9;E119;Diabetes mellitus, Typ 2: Ohne Komplikationen;Diabetes mellitus, Typ 2;Ohne Komplikationen;;P;P;
5;T;S;04;E10;E11.90;E11.90;E1190;Diabetes mellitus, Typ 2: Ohne Komplikationen: Nicht als entgleist bezeichnet;Diabetes mellitus, Typ 2;Ohne Komplikationen;Nicht als entgleist bezeichnet;P;P;
4;T;X;10;J00;J06.9;J06.9;J069;Akute Infektion der oberen Atemwege, nicht näher bezeichnet;Akute Infektionen an mehreren oder nicht näher bezeichneten Lokalisationen der oberen Atemwege;Akute Infektion der oberen Atemwege, nicht näher bezeichnet;;P;P;
"""


def _katalog(tmp_path: Path, inhalt: str = BFARM_ZEILEN, encoding: str = "utf-8") -> IcdKatalog:
    pfad = tmp_path / "icd10gm2099syst_kodes.txt"
    pfad.write_bytes(inhalt.encode(encoding))
    return IcdKatalog.aus_datei(pfad)


def test_bfarm_format(tmp_path):
    k = _katalog(tmp_path)
    assert len(k) == 4
    assert k.pruefen("E11.90").endstellig
    assert not k.pruefen("E11").endstellig
    assert k.pruefen("e1190").code == "E11.90"
    assert k.pruefen("X99.9") is None
    assert [e.code for e in k.unterkodes("E11")] == ["E11.9", "E11.90"]


def test_cp1252_und_einfaches_format(tmp_path):
    k = _katalog(tmp_path, "E11;Diabetes mellitus, Typ 2\nE11.90;Diabetes ohne Komplikationen\nJ06.9;Infektion, nicht näher bezeichnet\n", "cp1252")
    assert not k.pruefen("E11").endstellig
    assert k.pruefen("E11.90").endstellig
    assert "näher" in k.pruefen("J06.9").titel


def test_suche(tmp_path):
    k = _katalog(tmp_path)
    assert k.suchen("Diabetes Typ 2 entgleist")[0].code == "E11.90"
    assert k.suchen("obere atemwege")[0].code == "J06.9"
    assert [e.code for e in k.suchen("E11")] == ["E11", "E11.9", "E11.90"]
    assert k.suchen("xyzxyz") == []


class FakeClient:
    """Spielt eine Tool-Runde und dann eine JSON-Antwort ab."""

    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.anfragen = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.anfragen.append(kwargs)
        return self.antworten.pop(0)


def test_agentenschleife_prueft_codes(tmp_path):
    k = _katalog(tmp_path)
    ergebnis_json = {
        "codes": [
            {"code": "e11.90", "titel": "Diabetes", "diagnosesicherheit": "G", "seitenlokalisation": "keine", "begruendung": "DM2"},
            {"code": "E11", "titel": "Diabetes", "diagnosesicherheit": "V", "seitenlokalisation": "keine", "begruendung": "x"},
            {"code": "Q99.9", "titel": "Erfunden", "diagnosesicherheit": "G", "seitenlokalisation": "keine", "begruendung": "x"},
        ],
        "rueckfragen": [],
        "hinweise": [],
    }
    client = FakeClient([
        SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="t1", name="icd_suchen", input={"suchbegriff": "Diabetes"}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(ergebnis_json))]),
    ])

    e = kodieren("Diabetes mellitus Typ 2", k, client=client)

    tool_result = client.anfragen[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and "E11.90" in tool_result["content"]
    assert e["codes"][0]["code"] == "E11.90" and e["codes"][0]["im_katalog"] and e["codes"][0]["endstellig"]
    assert e["codes"][0]["titel"].startswith("Diabetes mellitus, Typ 2: Ohne")
    assert e["codes"][1]["endstellig"] is False
    assert e["codes"][2]["im_katalog"] is False
    assert e["katalog"] == "icd10gm2099syst_kodes.txt"


def test_ohne_katalog_keine_tools():
    antwort = {"codes": [{"code": "J06.9", "titel": "x", "diagnosesicherheit": "G", "seitenlokalisation": "keine", "begruendung": "x"}],
               "rueckfragen": [], "hinweise": []}
    client = FakeClient([SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(antwort))])])
    e = kodieren("Erkältung", None, client=client)
    assert "tools" not in client.anfragen[0]
    assert e["codes"][0]["im_katalog"] is None
