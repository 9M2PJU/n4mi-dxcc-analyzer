"""DX Monitor DXpeditions (D54): address, validation, name matching, tags, API.

All data here is synthetic, shaped like DX Monitor's /api/adxo and
/api/watched (checked against DX Monitor commit 6950a24). In the synthetic
credits every entity whose DXCC number is a multiple of 4 is never credited,
so it is on Missing Entities: e.g. Somalia 232, Mount Athos 180, San Andres
216, eSwatini 468, DPRK 344, Bouvet 24. Bangladesh 305 and the Solomon
Islands 185 are credited.
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import dxmon
from app.main import create_app
from conftest import render_paste

TODAY = date(2026, 10, 13)


def entry(id_, name, call, begin, end, active=False):
    return {"id": id_, "dxcc": name, "callsign": call, "begin": begin, "end": end,
            "active": active, "qsl": "LoTW", "source": "test", "info": ""}


ADXO = {"updated": "2026-10-13T19:21:44-04:00", "entry_count": 9, "entries": [
    entry("a1", "Somalia", "6O2M", "2026-10-05", "2026-10-25", True),          # on air, watched
    entry("a2", "Mount Athos", "SV2ASP/A", "2026-10-20", "2026-10-30"),        # soon, not watched
    entry("a3", "eSwatini", "3DA0GY", "2026-10-15", "2026-11-02"),             # built-in alias
    entry("a4", "San Andreas & Providencia", "HK0X", "2026-12-20", "2027-01-05"),  # later
    entry("a5", "Nth Korea", "P5X", "2026-10-14", "2026-10-20"),               # unplaced
    entry("a6", "Bangladesh", "S21HRG", "2026-10-16", "2026-10-20"),           # credited here
    entry("a7", "Solomon Is", "H44MS", "2026-10-03", "2026-11-20", True),      # credited here
    entry("a8", "Bouvet", "3Y0X", "2026-10-01", "2026-10-10", True),           # ended (stale flag)
    entry("a9", "Somalia", "6O6X", "2027-02-15", "2027-02-27"),                # 2nd Somalia, later
]}
WATCHED = {"count": 2, "entries": [
    {"id": "w1", "callsign": "6O2M", "dxcc": "Somalia", "source_adxo_id": "a1", "note": ""},
    {"id": "w2", "callsign": "3DA0GY", "dxcc": "Kingdom of Eswatini",
     "source_adxo_id": None, "note": "manual add"},
]}


NEEDED = {"count": 1, "entries": [
    {"id": "n1", "entity": "Somalia", "band": "", "mode": "", "note": "", "added": "x"}]}


def fake_dxmon(adxo=ADXO, watched=WATCHED, needed=NEEDED):
    calls = []

    def fetch(url, timeout=dxmon.TIMEOUT_S):
        calls.append(url)
        if url.endswith("/api/adxo"):
            return json.dumps(adxo).encode() if not isinstance(adxo, bytes) else adxo
        if url.endswith("/api/watched"):
            return json.dumps(watched).encode() if not isinstance(watched, bytes) else watched
        if url.endswith("/api/needed"):
            if isinstance(needed, Exception):
                raise needed
            return json.dumps(needed).encode() if not isinstance(needed, bytes) else needed
        raise AssertionError(url)
    fetch.calls = calls
    return fetch


@pytest.fixture
def matcher(reference):
    return dxmon.Matcher(reference, dxmon.load_builtin_aliases(reference), {})


# ---------- address ----------

@pytest.mark.parametrize("raw, tidy", [
    ("http://192.168.6.29:8083", "http://192.168.6.29:8083"),
    (" http://192.168.6.29:8083/ ", "http://192.168.6.29:8083"),
    ("https://dxmon.lan", "https://dxmon.lan"),
    ("", ""), ("   ", ""),
])
def test_check_url_accepts(raw, tidy):
    assert dxmon.check_url(raw) == tidy


@pytest.mark.parametrize("raw", [
    "192.168.6.29:8083", "ftp://host", "http://", "http://host/api/adxo",
    "http://user:pw@host:8083", "http://host:8083?x=1", "http://host:port", "x" * 300,
])
def test_check_url_rejects(raw):
    with pytest.raises(ValueError):
        dxmon.check_url(raw)


# ---------- validation ----------

def test_parse_adxo_keeps_good_entries_and_skips_bad():
    data = dict(ADXO, entries=ADXO["entries"] + [
        {"id": "", "dxcc": "X", "callsign": "Y", "begin": "2026-10-01", "end": "2026-10-02"},
        entry("b2", "Somalia", "6O1A", "2026-13-01", "2026-12-02"),    # impossible date
        entry("b3", "Somalia", "6O1B", "2026-11-05", "2026-11-01"),    # ends before it starts
        "not an object",
    ])
    updated, entries, skipped = dxmon.parse_adxo(json.dumps(data))
    assert updated == ADXO["updated"] and len(entries) == 9 and skipped == 4
    assert entries[0] == {"id": "a1", "name": "Somalia", "callsign": "6O2M",
                          "begin": "2026-10-05", "end": "2026-10-25"}


@pytest.mark.parametrize("data", [b"<html>Bad gateway</html>", b"[]", b'{"entries": 5}', b""])
def test_parse_adxo_rejects_wrong_shapes(data):
    with pytest.raises(dxmon.DXMonError):
        dxmon.parse_adxo(data)


def test_parse_adxo_rejects_huge_list():
    big = {"entries": [entry(str(i), "Somalia", "6O", "2026-10-01", "2026-10-02")
                       for i in range(dxmon.MAX_ENTRIES + 1)]}
    with pytest.raises(dxmon.DXMonError):
        dxmon.parse_adxo(json.dumps(big))


def test_fetch_needs_both_lists():
    with pytest.raises(dxmon.DXMonError):
        dxmon.fetch("http://x", fake_dxmon(watched=b"<html>404</html>"))
    data = dxmon.fetch("http://x", fake_dxmon())
    assert len(data["entries"]) == 9 and len(data["watched"]) == 2


# ---------- names ----------

def test_builtin_aliases_all_name_current_entities(reference):
    builtin = dxmon.load_builtin_aliases(reference)
    assert builtin[dxmon.normalize("Dem Rep Congo")] == 414
    assert builtin[dxmon.normalize("Sint Maartin")] == 518      # ADXO's misspelling
    assert builtin[dxmon.normalize("St Martin")] == 213
    assert len(builtin) >= 13


def test_builtin_alias_file_with_a_bad_row_refuses_to_load(reference, tmp_path):
    bad = tmp_path / "a.csv"
    bad.write_text("adxo_name,dxcc,note\nSomewhere,9999,typo\n")
    with pytest.raises(ValueError):
        dxmon.load_builtin_aliases(reference, bad)


@pytest.mark.parametrize("name, dxcc, how", [
    ("Somalia", 232, "direct"),
    ("SOMALIA ", 232, "direct"),
    ("Solomon Is", 185, "direct"),            # "Is" spelt out
    ("Br Virgin Is", 65, "direct"),           # "Br" spelt out
    ("Mount Athos", 180, "direct"),
    ("Dem Rep Congo", 414, "builtin"),
    ("eSwatini", 468, "builtin"),
    ("Peter I", 199, "builtin"),
    ("Nth Korea", None, "unplaced"),
])
def test_place(matcher, name, dxcc, how):
    p = matcher.place(name)
    assert (p.dxcc, p.how) == (dxcc, how)


def test_dan_decisions_apply_and_ignore(reference):
    m = dxmon.Matcher(reference, dxmon.load_builtin_aliases(reference),
                      {dxmon.normalize("Nth Korea"): 344, dxmon.normalize("Atlantis"): None})
    assert (m.place("Nth Korea").dxcc, m.place("Nth Korea").how) == (344, "approved")
    assert (m.place("Atlantis").dxcc, m.place("Atlantis").how) == (None, "ignored")


def test_suggestion_is_offered_but_never_applied(matcher):
    s = matcher.suggest("Mount Athoss")
    assert s and s["dxcc"] == 180
    assert matcher.place("Mount Athoss").how == "unplaced"
    assert matcher.suggest("Zzqx") is None


# ---------- tags ----------

def _cache():
    return dxmon.fetch("http://x", fake_dxmon())


NEEDED = {232, 180, 216, 468, 344, 24}


def test_build_tags_window_watched_and_summary(matcher):
    v = dxmon.build(_cache(), matcher, NEEDED, TODAY)
    t = v["tags"]
    assert t["232"] == [{"kind": "air", "callsign": "6O2M", "begin": "2026-10-05",
                         "end": "2026-10-25", "watched": True}]          # 6O6X is beyond 30 days
    assert t["180"][0]["kind"] == "soon" and t["180"][0]["watched"] is False
    assert t["468"][0]["watched"] is True             # manual Watched entry, matched by call
    assert "216" not in t                             # starts after the 30-day window
    assert "24" not in t                              # ended, though the feed still says active
    assert "305" not in t and "185" not in t          # credited, so not on Missing Entities
    assert "344" not in t                             # its ADXO name isn't placed yet
    assert v["summary"] == {"on_air": 1, "soon": 2, "not_watched": 1, "later": 1}
    assert [u["name"] for u in v["unplaced"]] == ["Nth Korea"]
    assert v["names"]["names"] == 8 and v["names"]["unplaced"] == 1


def test_build_uses_today_not_the_feeds_active_flag(matcher):
    v = dxmon.build(_cache(), matcher, NEEDED, date(2026, 10, 26))
    assert "232" not in v["tags"]                     # 6O2M ended on the 25th
    assert v["tags"]["180"][0]["kind"] == "air"       # Mount Athos started on the 20th


def test_build_with_nothing_needed(matcher):
    v = dxmon.build(_cache(), matcher, set(), TODAY)
    assert v["tags"] == {} and v["summary"]["on_air"] == 0


# ---------- API ----------

def make_client(tmp_path, reference, fetch):
    app = create_app(db_path=tmp_path / "d.db", reference=reference,
                     clublog_fetch=lambda: b"{}", dxmon_fetch=fetch, today=lambda: TODAY)
    return TestClient(app)


def test_off_by_default_and_never_calls_out(tmp_path, reference, credits):
    fetch = fake_dxmon()
    with make_client(tmp_path, reference, fetch) as c:
        c.post("/api/import/preview", data={"text": render_paste(reference, credits)})
        assert c.get("/api/dxmon").json() == {"enabled": False}
        assert c.post("/api/dxmon/refresh").status_code == 409
        assert c.get("/api/settings/dxmon").json() == {"url": ""}
    assert fetch.calls == []


def test_save_address_fetches_and_tags(tmp_path, reference, credits):
    fetch = fake_dxmon()
    with make_client(tmp_path, reference, fetch) as c:
        p = c.post("/api/import/preview", data={"text": render_paste(reference, credits)}).json()
        c.post(f"/api/import/{p['id']}/save")
        assert c.put("/api/settings/dxmon", json={"url": "dxmon:8083"}).status_code == 422
        v = c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083/"}).json()
        assert v["enabled"] and v["ok"] and v["url"] == "http://dxmon.lan:8083"
        assert v["entry_count"] == 9 and v["watched_count"] == 2
        assert v["tags"]["232"][0]["kind"] == "air" and v["summary"]["on_air"] == 1
        assert fetch.calls == ["http://dxmon.lan:8083/api/adxo", "http://dxmon.lan:8083/api/watched",
                               "http://dxmon.lan:8083/api/needed"]
        # Opening Missing Entities again within 15 minutes uses the stored copy.
        assert c.get("/api/dxmon").json()["tags"] == v["tags"]
        assert len(fetch.calls) == 3


def test_auto_refresh_after_15_minutes(tmp_path, reference):
    fetch = fake_dxmon()
    with make_client(tmp_path, reference, fetch) as c:
        c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"})
        assert len(fetch.calls) == 3
        conn = __import__("sqlite3").connect(tmp_path / "d.db")
        conn.execute("UPDATE external_data SET fetched_at = '2026-01-01T00:00:00+00:00' "
                     "WHERE name = 'dxmon_attempt'")
        conn.commit()
        conn.close()
        c.get("/api/dxmon")
        assert len(fetch.calls) == 6


def test_failure_keeps_last_good_copy(tmp_path, reference, credits):
    state = {"down": False}
    good = fake_dxmon()

    def fetch(url, timeout=dxmon.TIMEOUT_S):
        if state["down"]:
            raise dxmon.DXMonError("DX Monitor didn't answer (no reply within 5 seconds).")
        return good(url)
    with make_client(tmp_path, reference, fetch) as c:
        p = c.post("/api/import/preview", data={"text": render_paste(reference, credits)}).json()
        c.post(f"/api/import/{p['id']}/save")
        first = c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"}).json()
        state["down"] = True
        v = c.post("/api/dxmon/refresh").json()
        assert v["ok"] is False and "didn't answer" in v["error"]
        assert v["fetched_at"] == first["fetched_at"] and v["tags"] == first["tags"]
        # Garbage instead of JSON is a failure too, never stored.
        state["down"] = False
        bad = fake_dxmon(adxo=b"<html>502</html>")
        c.app.state.dxmon_fetch = bad
        v = c.post("/api/dxmon/refresh").json()
        assert v["ok"] is False and v["tags"] == first["tags"]


def test_changing_the_address_fetches_again(tmp_path, reference):
    fetch = fake_dxmon()
    with make_client(tmp_path, reference, fetch) as c:
        c.put("/api/settings/dxmon", json={"url": "http://a.lan:8083"})
        c.put("/api/settings/dxmon", json={"url": "http://b.lan:8083"})
        assert fetch.calls[-1] == "http://b.lan:8083/api/needed"
        assert c.put("/api/settings/dxmon", json={"url": ""}).json() == {"enabled": False}


def test_approve_ignore_and_remove_names(tmp_path, reference, credits):
    with make_client(tmp_path, reference, fake_dxmon()) as c:
        p = c.post("/api/import/preview", data={"text": render_paste(reference, credits)}).json()
        c.post(f"/api/import/{p['id']}/save")
        v = c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"}).json()
        assert [u["name"] for u in v["unplaced"]] == ["Nth Korea"] and "344" not in v["tags"]
        assert c.post("/api/dxmon/names", json={"name": "Nth Korea", "dxcc": 196}).status_code == 422
        v = c.post("/api/dxmon/names", json={"name": "Nth Korea", "dxcc": 344}).json()
        assert v["unplaced"] == [] and v["tags"]["344"][0]["callsign"] == "P5X"
        assert v["decisions"][0]["entity"] == "DPRK (NORTH KOREA)"
        key = v["decisions"][0]["name_norm"]
        v = c.post("/api/dxmon/names", json={"name": "Nth Korea", "dxcc": None}).json()
        assert "344" not in v["tags"] and v["unplaced"] == [] and v["decisions"][0]["dxcc"] is None
        v = c.delete("/api/dxmon/names", params={"name_norm": key}).json()
        assert [u["name"] for u in v["unplaced"]] == ["Nth Korea"] and v["decisions"] == []
        assert c.delete("/api/dxmon/names", params={"name_norm": key}).status_code == 404


def test_test_connection_does_not_save(tmp_path, reference):
    with make_client(tmp_path, reference, fake_dxmon()) as c:
        r = c.post("/api/dxmon/test", json={"url": "http://dxmon.lan:8083"}).json()
        assert r["ok"] and r["entry_count"] == 9
        assert c.get("/api/settings/dxmon").json() == {"url": ""}
        assert c.post("/api/dxmon/test", json={"url": ""}).status_code == 422
    with make_client(tmp_path, reference, fake_dxmon(adxo=b"nope")) as c:
        r = c.post("/api/dxmon/test", json={"url": "http://dxmon.lan:8083"}).json()
        assert r["ok"] is False and "JSON" in r["error"]


def test_before_any_import_dxmon_still_answers(tmp_path, reference):
    with make_client(tmp_path, reference, fake_dxmon()) as c:
        v = c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"}).json()
        assert v["ok"] and v["tags"] == {}


# ---------- added after the independent review (2026-10-13) ----------

import threading                                   # noqa: E402
import time                                        # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer   # noqa: E402
from types import SimpleNamespace                  # noqa: E402


@pytest.mark.parametrize("entries", [
    [],                                                                    # DX Monitor not ready
    [dict(e, begin="2026-10-16T00:00:00Z") for e in ADXO["entries"]],       # format changed
    [dict(e, end="soon") for e in ADXO["entries"][:5]] + ADXO["entries"][:3],  # mostly unreadable
])
def test_empty_or_mostly_unreadable_list_is_a_failure(entries):
    with pytest.raises(dxmon.DXMonError):
        dxmon.parse_adxo(json.dumps({"entries": entries}))


def test_empty_list_keeps_the_last_good_copy(tmp_path, reference, credits):
    with make_client(tmp_path, reference, fake_dxmon()) as c:
        p = c.post("/api/import/preview", data={"text": render_paste(reference, credits)}).json()
        c.post(f"/api/import/{p['id']}/save")
        first = c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"}).json()
        c.app.state.dxmon_fetch = fake_dxmon(adxo={"updated": "x", "entries": []})
        v = c.post("/api/dxmon/refresh").json()
        assert v["ok"] is False and "no usable" in v["error"]
        assert v["tags"] == first["tags"] and v["summary"] == first["summary"]


def test_watched_failing_through_the_api_keeps_the_last_good_copy(tmp_path, reference, credits):
    with make_client(tmp_path, reference, fake_dxmon()) as c:
        p = c.post("/api/import/preview", data={"text": render_paste(reference, credits)}).json()
        c.post(f"/api/import/{p['id']}/save")
        first = c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"}).json()
        c.app.state.dxmon_fetch = fake_dxmon(watched=b"<html>500</html>")
        v = c.post("/api/dxmon/refresh").json()
        assert v["ok"] is False and v["fetched_at"] == first["fetched_at"]
        assert v["tags"] == first["tags"]


def test_a_list_from_a_different_address_is_never_shown(tmp_path, reference, credits):
    with make_client(tmp_path, reference, fake_dxmon()) as c:
        p = c.post("/api/import/preview", data={"text": render_paste(reference, credits)}).json()
        c.post(f"/api/import/{p['id']}/save")
        assert c.put("/api/settings/dxmon", json={"url": "http://a.lan:8083"}).json()["tags"]

        def down(url, timeout=dxmon.TIMEOUT_S):
            raise dxmon.DXMonError("DX Monitor didn't answer (no reply within 5 seconds).")
        c.app.state.dxmon_fetch = down
        v = c.put("/api/settings/dxmon", json={"url": "http://b.lan:8083"}).json()
        assert v["ok"] is False and v["fetched_at"] is None and "tags" not in v
        # Back to the first address: its stored list is valid again.
        v = c.get("/api/dxmon", params={"auto": "false"}).json()
        assert "tags" not in v
        c.app.state.dxmon_fetch = fake_dxmon()
        v = c.put("/api/settings/dxmon", json={"url": "http://a.lan:8083"}).json()
        assert v["ok"] and v["tags"]


def test_settings_view_never_fetches(tmp_path, reference):
    fetch = fake_dxmon()
    with make_client(tmp_path, reference, fetch) as c:
        c.put("/api/settings/dxmon", json={"url": "http://dxmon.lan:8083"})
        n = len(fetch.calls)
        conn = __import__("sqlite3").connect(tmp_path / "d.db")
        conn.execute("UPDATE external_data SET fetched_at = '2026-01-01T00:00:00+00:00' "
                     "WHERE name = 'dxmon_attempt'")
        conn.commit()
        conn.close()
        c.get("/api/dxmon", params={"auto": "false"})
        assert len(fetch.calls) == n            # stale, but Settings doesn't fetch
        c.get("/api/dxmon")
        assert len(fetch.calls) == n + 3        # Missing Entities does


def test_your_decision_outranks_the_builtin_list(reference):
    builtin = dxmon.load_builtin_aliases(reference)
    m = dxmon.Matcher(reference, builtin, {dxmon.normalize("Gambia"): None})
    assert m.place("Gambia").how == "ignored"
    m = dxmon.Matcher(reference, builtin, {dxmon.normalize("Gambia"): 422})
    assert (m.place("Gambia").dxcc, m.place("Gambia").how) == (422, "approved")


def test_a_name_matching_two_entities_stays_unplaced():
    ents = [SimpleNamespace(dxcc=1, lotw_name="FOO ISLAND", adif_name="FOO ISLAND", prefix="F1"),
            SimpleNamespace(dxcc=2, lotw_name="FOO ISLANDS", adif_name="FOO ISLANDS", prefix="F2")]
    m = dxmon.Matcher(SimpleNamespace(current=ents), {}, {})
    assert m.place("Foo Is").how == "unplaced"        # could be either: never guess
    assert m.place("Foo Islands").dxcc == 2


def test_watched_id_must_agree_on_call_or_entity(matcher):
    cache = _cache()
    cache["watched"] = [{"source_adxo_id": "a2", "name": "Japan", "callsign": "JA1XYZ"}]
    v = dxmon.build(cache, matcher, NEEDED, TODAY)
    assert v["tags"]["180"][0]["watched"] is False    # id matches, but call and entity don't
    cache["watched"] = [{"source_adxo_id": "a2", "name": "Mt Athos", "callsign": "SV2ASP/A"}]
    assert dxmon.build(cache, matcher, NEEDED, TODAY)["tags"]["180"][0]["watched"] is True


def test_names_differing_only_in_case_are_one_name(matcher):
    cache = _cache()
    cache["entries"].append(dict(cache["entries"][4], id="z", name="NTH KOREA"))
    v = dxmon.build(cache, matcher, NEEDED, TODAY)
    assert [u["name"] for u in v["unplaced"]] == ["Nth Korea"] and v["names"]["names"] == 8


# fetch_raw against a real local web server

class _Handler(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.mode == "500":
            self.send_response(500)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.mode == "big":
            self.wfile.write(b"x" * (dxmon.MAX_BYTES + 10))
        elif self.mode == "trickle":
            try:
                for _ in range(30):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.2)
            except OSError:
                pass
        else:
            self.wfile.write(json.dumps(ADXO).encode())


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_fetch_raw_real_http(server):
    _Handler.mode = "ok"
    assert json.loads(dxmon.fetch_raw(server + "/api/adxo"))["entry_count"] == 9
    _Handler.mode = "500"
    with pytest.raises(dxmon.DXMonError, match="HTTP 500"):
        dxmon.fetch_raw(server + "/api/adxo")
    _Handler.mode = "big"
    with pytest.raises(dxmon.DXMonError, match="larger"):
        dxmon.fetch_raw(server + "/api/adxo")


def test_fetch_raw_overall_deadline(server):
    _Handler.mode = "trickle"                 # a byte every 0.2 s: never trips the read timeout
    t = time.monotonic()
    with pytest.raises(dxmon.DXMonError, match="finish answering"):
        dxmon.fetch_raw(server + "/api/adxo", timeout=2, deadline=1)
    assert time.monotonic() - t < 3


def test_fetch_raw_refused_port():
    with pytest.raises(dxmon.DXMonError, match="connection refused"):
        dxmon.fetch_raw("http://127.0.0.1:1/api/adxo")
