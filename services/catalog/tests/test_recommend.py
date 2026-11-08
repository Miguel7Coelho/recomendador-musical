import pytest

from app import recommend as r


def test_camelot_exemplo_da_especificacao() -> None:
    assert r.camelot_neighbors("11A") == {"10A", "12A", "11B"}
    assert r.camelot_neighbors("1B") == {"12B", "2B", "1A"}
    assert r.camelot_neighbors("12A") == {"11A", "1A", "12B"}


@pytest.mark.parametrize(
    ("q", "c", "v"), [("11A", "11A", 1.0), ("11A", "12A", 0.7), ("11A", "11B", 0.7),
                      ("11A", "5B", 0.0), (None, "11A", 0.0)],
)  # fmt: skip
def test_key_match(q, c, v) -> None:
    assert r.key_match(q, c) == v


def test_genre_match() -> None:
    q = {"Pop---Synth-pop": 0.6, "Electronic---House": 0.4}
    assert r.genre_match(q, q) == pytest.approx(1.0)
    assert r.genre_match(q, {"Pop---Synth-pop": 0.3}) == pytest.approx(0.3)
    assert r.genre_match(q, {"Rock---Punk": 0.9}) == 0.0
    assert r.genre_match(None, q) == 0.0


@pytest.mark.parametrize(
    ("q", "c", "v"),
    [
        ({"vocal_presence": 0.9, "vocal_gender": "female", "vocal_confidence": 0.8},
         {"vocal_presence": 0.8, "vocal_gender": "female", "vocal_confidence": 0.9}, 0.8),
        ({"vocal_presence": 0.9, "vocal_gender": "female", "vocal_confidence": 0.8},
         {"vocal_presence": 0.8, "vocal_gender": "male", "vocal_confidence": 0.9}, 0.0),
        ({"vocal_presence": 0.0}, {"vocal_presence": 0.1}, 1.0),
        ({"vocal_presence": 0.0}, {"vocal_presence": 0.9, "vocal_gender": "male"}, 0.0),
        ({"vocal_presence": 0.9, "vocal_gender": "female"}, {"vocal_presence": 0.6}, 0.5),
        ({}, {"vocal_presence": 0.6}, 0.0),
    ],
)  # fmt: skip
def test_voice_match(q, c, v) -> None:
    assert r.voice_match(q, c) == pytest.approx(v)


def test_rank_ordena_e_explica() -> None:
    q = {"camelot": "11A", "bpm": 102, "styles": {"Pop---Synth-pop": 0.6}, "genre_top": "Pop",
         "vocal_presence": 0.9, "vocal_gender": "female", "vocal_confidence": 0.8}  # fmt: skip
    a = {"id": "a", "cosine": 0.70, "camelot": "11A", "bpm": 104,
         "styles": {"Pop---Synth-pop": 0.5}, "genre_top": "Pop", "vocal_presence": 0.8,
         "vocal_gender": "female", "vocal_confidence": 0.9}  # fmt: skip
    b = {"id": "b", "cosine": 0.80, "camelot": "4B", "bpm": 150, "styles": {"Rock---Punk": 0.9},
         "genre_top": "Rock", "vocal_presence": 0.1}  # fmt: skip
    out = r.rank(q, [b, a])
    assert [x["id"] for x in out] == ["a", "b"]  # cosseno menor, mas tom, estilo e voz batem
    assert out[0]["explanation"] == "mesmo tom 11A · synth-pop · vocal feminino · 104 vs. 102 BPM"
    assert out[1]["explanation"] == ""
    assert out[0]["score"] == pytest.approx(
        0.55 * 0.70 + 0.20 * 1.0 + 0.15 * (0.5 / 0.6) + 0.10 * 0.8, abs=1e-3
    )


def test_bpm_meio_tempo_conta_na_explicacao() -> None:
    q = {"bpm": 140.0}
    c = {"bpm": 70.5}
    comps = {"key": 0, "voice": 0}
    assert r.explain(q, c, comps) == "70 vs. 140 BPM"


def test_plano_de_relaxamento() -> None:
    start = {"key": "exact", "genre": "style", "voice": "on"}
    plan = r.relaxation_plan(start, locked=set())
    assert [tuple(p.values()) for p in plan] == [
        ("exact", "style", "on"), ("compatible", "style", "on"), ("off", "style", "on"),
        ("off", "genre", "on"), ("off", "off", "on"), ("off", "off", "off"),
    ]  # fmt: skip


def test_plano_respeita_travas() -> None:
    start = {"key": "exact", "genre": "style", "voice": "on"}
    plan = r.relaxation_plan(start, locked={"key", "voice"})
    assert all(p["key"] == "exact" and p["voice"] == "on" for p in plan)
    assert [p["genre"] for p in plan] == ["style", "genre", "off"]


def test_conditions() -> None:
    q = {"camelot": "11A", "styles": {"A---x": 0.5, "B---y": 0.3, "C---z": 0.1, "D---w": 0.05},
         "genre_top": "A", "vocal_presence": 0.9, "vocal_gender": "female",
         "vocal_confidence": 0.8}  # fmt: skip
    c = r.conditions(q, {"key": "compatible", "genre": "style", "voice": "on"})
    assert c["keys"] == ["10A", "11A", "11B", "12A"]
    assert c["styles"] == ["A---x", "B---y", "C---z"] and c["genre"] is None
    assert c["voice"] == {"vocal": True, "gender": "female"}
    c = r.conditions(q, {"key": "off", "genre": "genre", "voice": "off"})
    assert c == {"keys": None, "styles": None, "genre": "A", "voice": None}


def test_voz_em_duvida_nao_filtra() -> None:
    c = r.conditions({"vocal_presence": 0.5}, {"key": "off", "genre": "off", "voice": "on"})
    assert c["voice"] is None
    c = r.conditions({"vocal_presence": 0.0}, {"key": "off", "genre": "off", "voice": "on"})
    assert c["voice"] == {"vocal": False}


def test_cascata_relaxa_ate_ter_candidatas() -> None:
    q = {"camelot": "11A", "styles": {"A---x": 1.0}, "genre_top": "A", "vocal_presence": 0.0}
    seen = []

    def fetch(cond):
        seen.append(cond)
        n = 5 if cond["keys"] == ["11A"] else 30  # tom exato acha poucas
        return [{"id": str(i)} for i in range(n)]

    cands, levels, relaxed = r.run_cascade(
        q, {"key": "exact", "genre": "style", "voice": "on"}, set(), fetch, 20
    )
    assert len(cands) == 30 and len(seen) == 2
    assert levels["key"] == "compatible" and relaxed == ["key: exact → compatible"]


def test_cascata_sem_candidatas_suficientes_devolve_a_mais_solta() -> None:
    def fetch(cond):
        return [{"id": "1"}]

    cands, levels, _ = r.run_cascade(
        {"camelot": "1A"}, {"key": "exact", "genre": "style", "voice": "on"}, {"key"}, fetch, 20
    )
    assert levels == {"key": "exact", "genre": "off", "voice": "off"} and len(cands) == 1
