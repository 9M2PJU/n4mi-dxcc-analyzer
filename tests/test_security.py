"""Security review fixes (2026-10-21): DXCC-01, DXCC-02 (redirects), DXCC-04.

Everything here uses dummy files, synthetic workbooks and local throwaway HTTP
servers; nothing reaches a real service.
"""

import http.server
import io
import threading
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import dxmon
from app.main import PAGES, STATIC_DIR, create_app
from app.parser import XLSX_MAX_COLS, XLSX_MAX_ROWS, UploadError, parse_upload
from conftest import render_xlsx


# ---------- DXCC-01: page routes can't be made to serve other files ----------

@pytest.fixture
def client(tmp_path, reference):
    return TestClient(create_app(db_path=tmp_path / "d.db", reference=reference))


def test_page_routes_ignore_a_page_parameter(client, tmp_path):
    secret = tmp_path / "dummy_secret.txt"
    secret.write_text("DUMMY-OUTSIDE-STATIC")
    attempts = ["../app/main.py", "../requirements.txt", str(secret), str(tmp_path / "d.db"),
                "entities.html/../../app/main.py"]
    for path, page in PAGES.items():
        want = (STATIC_DIR / page).read_bytes()
        for q in attempts:
            r = client.get(path, params={"page": q})
            assert r.status_code == 200 and r.content == want, (path, q)
            assert b"DUMMY-OUTSIDE-STATIC" not in r.content and b"SQLite" not in r.content


def test_pages_and_static_still_work(client):
    for path, page in PAGES.items():
        r = client.get(path)
        assert r.status_code == 200 and r.content == (STATIC_DIR / page).read_bytes()
    assert client.get("/static/style.css").status_code == 200
    # StaticFiles refuses to leave its folder.
    assert client.get("/static/../app/main.py").status_code == 404
    assert client.get("/static/%2e%2e/app/main.py").status_code == 404


def test_no_route_takes_a_file_name(client):
    # Every page endpoint takes no parameters at all.
    routes = [r for r in client.app.routes if getattr(r, "path", None) in PAGES]
    assert len(routes) == len(PAGES)
    for r in routes:
        assert not r.dependant.query_params and not r.dependant.path_params


# ---------- DXCC-04: oversized workbooks are refused before a grid is built ----------

def _sheet_xml(dimension, rows_xml):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<dimension ref="{dimension}"/><sheetData>{rows_xml}</sheetData></worksheet>')


def _patched_xlsx(sheet_xml):
    """A real workbook (from openpyxl) with its first sheet replaced."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active["A1"] = "x"
    buf = io.BytesIO()
    wb.save(buf)
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                data = sheet_xml.encode()
            z.writestr(item, data)
    return out.getvalue()


def test_normal_workbook_still_imports(reference, credits):
    p = parse_upload("matrix.xlsx", render_xlsx(reference, credits))
    assert p.callsign == "N0CALL"


def test_declared_oversized_sheet_is_refused(monkeypatch):
    # Two real rows, but the sheet declares 5,000 rows by 100 columns.
    data = _patched_xlsx(_sheet_xml("A1:CV5000",
                                    '<row r="1"><c r="A1" t="inlineStr"><is><t>a</t></is></c></row>'
                                    '<row r="5000"><c r="CV5000"><v>1</v></c></row>'))
    assert len(data) < 10_000
    built = []
    import app.parser as parser
    monkeypatch.setattr(parser, "parse_cells", lambda rows: built.append(rows))
    with pytest.raises(UploadError, match="more than"):
        parse_upload("bomb.xlsx", data)
    assert built == []                     # validation never saw a big grid


def test_undeclared_long_sheet_stops_counting(monkeypatch):
    rows = "".join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, XLSX_MAX_ROWS + 50))
    data = _patched_xlsx(_sheet_xml("A1", rows))      # lies about its size
    with pytest.raises(UploadError, match="more than"):
        parse_upload("long.xlsx", data)


def test_wide_row_is_refused():
    col = "CV"     # column 100 > XLSX_MAX_COLS
    assert XLSX_MAX_COLS < 100
    data = _patched_xlsx(_sheet_xml("A1", f'<row r="1"><c r="{col}1"><v>1</v></c></row>'))
    with pytest.raises(UploadError, match="more than"):
        parse_upload("wide.xlsx", data)


def test_highly_compressed_workbook_is_refused():
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/sharedStrings.xml", b"0" * (60 * 1024 * 1024))   # 60 MB unpacked
    data = out.getvalue()
    assert len(data) < 200_000
    with pytest.raises(UploadError, match="unpacked"):
        parse_upload("zipbomb.xlsx", data)


def test_one_giant_row_is_refused_before_parsing():
    # One <row> of a million cells: small when compressed, huge for openpyxl.
    cells = "<c><v>1</v></c>" * 1_000_000
    data = _patched_xlsx(_sheet_xml("A1", f'<row r="1">{cells}</row>'))
    assert len(data) < 200_000
    with pytest.raises(UploadError, match="unpacked"):
        parse_upload("giant_row.xlsx", data)


def test_styles_bomb_is_refused_before_parsing():
    import openpyxl
    wb = openpyxl.Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    out = io.BytesIO()
    xfs = "<xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/>" * 300_000
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "xl/styles.xml":
                data = ('<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/'
                        f'spreadsheetml/2006/main"><cellXfs count="300000">{xfs}</cellXfs></styleSheet>').encode()
            z.writestr(item, data)
    with pytest.raises(UploadError, match="unpacked"):
        parse_upload("styles.xlsx", out.getvalue())


def test_api_map_is_not_published(client):
    assert client.get("/openapi.json").status_code == 404


def test_not_a_zip_is_refused_cleanly():
    with pytest.raises(UploadError, match="valid .xlsx"):
        parse_upload("fake.xlsx", b"not a zip at all")


def test_import_endpoint_rejects_an_oversized_workbook(client):
    rows = "".join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, XLSX_MAX_ROWS + 50))
    data = _patched_xlsx(_sheet_xml("A1", rows))
    r = client.post("/api/import/preview", files={"file": ("long.xlsx", data)})
    assert r.status_code in (400, 422) and "more than" in r.text
    assert client.get("/api/snapshots").json().get("snapshots", []) == []
    assert client.get("/healthz").status_code == 200


# ---------- DXCC-02: DX Monitor redirects are never followed ----------

def _serve(handler_cls):
    srv = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_redirect_is_refused_and_target_never_contacted(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    hits = []

    class Target(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"entries": []}')

        def log_message(self, *a):
            pass

    target = _serve(Target)

    class Redirector(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/internal/admin")
            self.end_headers()

        def log_message(self, *a):
            pass

    redir = _serve(Redirector)
    try:
        with pytest.raises(dxmon.DXMonError, match="redirect"):
            dxmon.fetch_raw(f"http://127.0.0.1:{redir.server_port}/api/adxo")
        assert hits == []
    finally:
        target.shutdown()
        redir.shutdown()


def test_plain_answer_still_works(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    class Ok(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *a):
            pass

    srv = _serve(Ok)
    try:
        assert dxmon.fetch_raw(f"http://127.0.0.1:{srv.server_port}/api/adxo") == b'{"ok": true}'
    finally:
        srv.shutdown()
