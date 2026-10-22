"""In-app user guide (D58), version number, and wrong-table messages."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import guide
from app.main import create_app
from app.parser import parse_text
from app.status_check import parse_status
from app.version import VERSION
from conftest import render_paste
from test_status_check import status_text

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, reference):
    return TestClient(create_app(db_path=tmp_path / "d.db", reference=reference))


@pytest.fixture
def help_html(client):
    r = client.get("/help")
    assert r.status_code == 200
    return r.text


# ---------- the Help page ----------

def test_every_guide_section_is_on_the_help_page(help_html):
    src = (ROOT / "User_Guide.md").read_text(encoding="utf-8")
    headings = re.findall(r"^#{2,3} (.+)$", src, flags=re.M)
    headings.remove("Contents")
    for h in headings:
        assert f">{h.replace(chr(39), '&rsquo;')}<" in help_html or f">{h}<" in help_html, h


def test_contents_panel_replaces_the_guides_own_list(help_html):
    article = help_html.split('<article class="doc">', 1)[1]
    assert 'id="contents"' not in article          # the guide's list is dropped
    toc = help_html.split('<aside class="toc', 1)[1].split("</aside>", 1)[0]
    assert 'href="#getting-your-lotw-data-in-import"' in toc
    assert 'href="#checking-against-lotw-account-status"' in toc   # subsections listed


def test_every_image_on_the_help_page_loads(client, help_html):
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', help_html)
    assert len(srcs) >= 10
    for s in srcs:
        assert s.startswith("/images/"), s
        r = client.get(s)
        assert r.status_code == 200 and len(r.content) > 1000, s


def test_every_page_help_link_points_at_a_real_section(help_html):
    js = (ROOT / "static" / "common.js").read_text(encoding="utf-8")
    block = re.search(r"const HELP_SECTIONS = \{(.*?)\};", js, flags=re.S).group(1)
    sections = dict(re.findall(r"'(/[a-z]*)':\s*'([a-z0-9-]+)'", block))
    from app.main import PAGES
    assert set(sections) == set(PAGES)               # every page has a Help link
    for page, anchor in sections.items():
        assert f'id="{anchor}"' in help_html, (page, anchor)


def test_nested_lists_stay_nested(help_html):
    # "The check shows:" bullets sit inside step 2, as on GitHub.
    step = help_html.split("The check shows:", 1)[1].split("</ol>", 1)[0]
    assert "<ul>" in step and "each category" in step


def test_readme_link_goes_to_github(help_html):
    assert 'href="README.md"' not in help_html
    assert guide.README_URL in help_html


def test_help_route_takes_no_parameters(client):
    r = client.get("/help", params={"page": "../app/main.py"})
    assert r.status_code == 200 and "def create_app" not in r.text
    route = next(r for r in client.app.routes if getattr(r, "path", None) == "/help")
    assert not route.dependant.query_params and not route.dependant.path_params


def test_images_folder_does_not_leak_other_files(client):
    # The test client tidies "../" before sending, so ask the images mount
    # itself; a running server was also checked with curl --path-as-is.
    mount = next(r for r in client.app.routes if getattr(r, "path", None) == "/images")
    for p in ("../app/main.py", "../User_Guide.md", "../../etc/passwd", "..%2fapp%2fmain.py"):
        full, _ = mount.app.lookup_path(p)
        assert full == "", p
    assert mount.app.lookup_path("copy_matrix.svg")[0].endswith("copy_matrix.svg")


def test_missing_images_folder_gives_404_not_500(tmp_path, reference, monkeypatch):
    monkeypatch.setattr(guide, "IMAGES_DIR", tmp_path / "no_images")
    c = TestClient(create_app(db_path=tmp_path / "d.db", reference=reference))
    assert c.get("/images/copy_matrix.svg").status_code == 404
    assert c.get("/help").status_code == 200


def test_missing_guide_is_reported_not_fatal(tmp_path, reference):
    c = TestClient(create_app(db_path=tmp_path / "d.db", reference=reference,
                              guide_path=tmp_path / "nope.md"))
    r = c.get("/help")
    assert r.status_code == 200 and "Guide not available" in r.text
    assert c.get("/healthz").status_code == 200


def test_guide_rendering_on_its_own(tmp_path):
    p = tmp_path / "g.md"
    p.write_text("# Title\n\nIntro\n\n## Contents\n\n- [A](#a)\n\n## A\n\n1. one\n   - sub\n\n"
                 "![x](images/x.png) [r](README.md)\n", encoding="utf-8")
    g = guide.render(p)
    assert g.error is None
    assert "<h1" not in g.html and 'id="contents"' not in g.html
    assert g.toc == [("a", "A", [])]
    assert 'src="/images/x.png"' in g.html and guide.README_URL in g.html
    assert "<ol>\n<li>one<ul>" in g.html.replace("\n<ul>", "<ul>")


# ---------- version ----------

def test_status_reports_the_version(client):
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION)
    assert client.get("/api/status").json()["version"] == VERSION


def test_status_reports_the_version_when_the_data_folder_is_missing(tmp_path, reference, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "missing"))
    c = TestClient(create_app(reference=reference))
    st = c.get("/api/status").json()
    assert st["ok"] is False and st["version"] == VERSION


def test_header_shows_the_version_and_help_link():
    js = (ROOT / "static" / "common.js").read_text(encoding="utf-8")
    assert 'id="appver"' in js and "st.version" in js
    assert 'class="helplink"' in js


# ---------- wrong-table messages (Dan, 2026-10-21) ----------

def test_account_status_pasted_into_import_is_named(credits):
    r = parse_text(status_text(credits))
    assert not r.rows
    assert len(r.errors) == 1
    msg = r.errors[0]
    assert "Account Status table" in msg and "View Award Credit Matrix" in msg and "Settings" in msg


def test_matrix_pasted_into_status_check_is_named(reference, credits):
    r = parse_status(render_paste(reference, credits))
    assert not r.ok and len(r.errors) == 1
    assert "Award Credit Matrix" in r.errors[0] and "Import" in r.errors[0]


def test_ordinary_junk_keeps_the_ordinary_messages(credits):
    r = parse_text("hello\tthere\n1\t2")
    assert r.errors == [e for e in r.errors if "Account Status" not in e]
    assert "No LoTW matrix header found" in r.errors[0]
    s = parse_status("hello\tthere")
    assert "does not look like LoTW's DXCC Account Status table" in s.errors[0]


def test_arrl_footer_is_explained_and_still_rejected(reference, credits):
    text = render_paste(reference, credits).rstrip("\r\n") + (
        "\r\n\r\nReproduction of material from any ARRL web page without written permission "
        "is strictly prohibited.\r\n")
    r = parse_text(text)
    assert any("ARRL copyright line" in e for e in r.errors)


def test_changed_matrix_header_beside_status_table_keeps_the_header_message(reference, credits):
    # Both tables pasted, and LoTW has renamed "Deleted": the real problem is the
    # header, so the wrong-table hint must not hide it.
    text = status_text(credits) + "\r\n" + render_paste(reference, credits).replace("Deleted", "Del")
    r = parse_text(text)
    assert r.errors and not any("Account Status table" in e for e in r.errors)


def test_a_normal_paste_still_parses(reference, credits):
    r = parse_text(render_paste(reference, credits))
    assert not r.errors and r.callsign == "N0CALL"


def test_whole_page_with_status_box_above_still_imports(reference, credits):
    # Text above the banner is ignored, including the Account Status box.
    r = parse_text(status_text(credits) + "\r\n" + render_paste(reference, credits))
    assert not r.errors and r.callsign == "N0CALL"
