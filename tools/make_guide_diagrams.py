"""Development only: draws the two copy-selection diagrams in the user guide.

    python tools/make_guide_diagrams.py

They are schematics, not screenshots: generic table outlines with made-up
N0CALL data, showing where to start and stop selecting in LoTW. Real LoTW
pages carry Dan's credits, and the repository is public.
Writes images/copy_matrix.svg and images/copy_account_status.svg.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"
BG, PANEL, LINE, TEXT, MUTED, AMBER = "#0d1016", "#151a22", "#3a4352", "#ece6d8", "#9aa3b2", "#f5a524"
SEL = "rgba(80,140,255,0.28)"
F = "font-family:'IBM Plex Sans','Segoe UI',system-ui,sans-serif"
M = "font-family:'JetBrains Mono',Consolas,monospace"
WIDTH = 1000


def svg(height, body, title, width=WIDTH):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">\n<title>{title}</title>\n'
            f'<rect width="{width}" height="{height}" rx="12" fill="{BG}"/>\n' + "\n".join(body) + "\n</svg>\n")


def text(x, y, s, size=11, fill=TEXT, anchor="start", font=F, weight=400, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'style="{font};font-size:{size}px;font-weight:{weight}{extra}" fill="{fill}">{s}</text>')


def marker(x, y, label, anchor="start", note=None):
    dx = 14 if anchor == "start" else -14
    out = [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{AMBER}"/>',
           text(x + dx, y + 5, label, 14, AMBER, anchor, weight=600)]
    if note:
        out.append(text(x + dx, y + 22, note, 12, MUTED, anchor))
    return out


def grid_lines(xs, y, h):
    return [f'<line x1="{x:.1f}" y1="{y}" x2="{x:.1f}" y2="{y + h}" stroke="{LINE}"/>' for x in xs[1:-1]]


def matrix():
    cols = ["Prefix", "Entity", "Deleted", "Mix", "Ph", "CW", "RT", "SAT",
            "160", "80", "40", "30", "20", "17", "15", "12", "10", "6", "2"]
    widths = [40, 118, 46] + [24] * 16
    x0 = 230
    xs = [x0]
    for w in widths:
        xs.append(xs[-1] + w)
    width = xs[-1] - x0
    mid = lambda i: (xs[i] + xs[i + 1]) / 2          # noqa: E731
    body = [text(24, 28, "Award Credit Matrix (schematic, made-up data)", 13, MUTED)]
    top = y = 44
    body += [f'<rect x="{x0}" y="{y}" width="{width}" height="40" fill="{PANEL}" stroke="{LINE}"/>',
             text(x0 + width / 2, y + 17, "DXCC Award Credit Report", 13, anchor="middle", weight=600),
             text(x0 + width / 2, y + 33, "Your Name, N0CALL", 12, MUTED, "middle")]
    y += 40
    body.append(f'<rect x="{x0}" y="{y}" width="{width}" height="26" fill="{PANEL}" stroke="{LINE}"/>')
    body += [text(mid(i), y + 17, c, 9.5, MUTED, "middle", weight=600) for i, c in enumerate(cols)]
    body += grid_lines(xs, y, 26)
    y += 26

    def row(y, prefix, name, marks, deleted=False):
        out = [f'<rect x="{x0}" y="{y}" width="{width}" height="22" fill="{BG}" stroke="{LINE}"/>',
               text(xs[0] + 5, y + 15, prefix, 10, AMBER, font=M),
               text(xs[2] - 5, y + 15, name, 10, anchor="end")]
        if deleted:
            out.append(text(mid(2), y + 15, "Yes", 10, anchor="middle"))
        out += grid_lines(xs, y, 22)
        out += [text(mid(c), y + 15, "X", 10, anchor="middle", font=M) for c in marks]
        return out

    for prefix, name, marks in [("3A", "MONACO", [3, 6, 10, 12]), ("3B8", "MAURITIUS", [3, 5, 6, 9, 11, 12])]:
        body += row(y, prefix, name, marks)
        y += 22
    body.append(text(x0 + width / 2, y + 22, "… several hundred rows …", 13, MUTED, "middle"))
    y += 34
    body += row(y, "ZS", "SOUTH AFRICA", [3, 4, 6, 9, 10, 11, 12, 13, 14])
    y += 22
    body += row(y, "ZS9", "WALVIS BAY", [], deleted=True)
    y += 22
    body.insert(1, f'<rect x="{x0}" y="{top}" width="{width}" height="{y - top}" fill="{SEL}"/>')
    body.append(text(x0, y + 22, "(ARRL copyright line: leave it out)", 11, MUTED))
    body += marker(x0 - 12, top + 8, "Start: just before the banner", "end")
    body += marker(xs[-1] + 12, y - 11, "End: after the last cell", note="(2 m box, bottom row)")
    return svg(y + 44, body, "Copy the matrix from the DXCC Award Credit Report banner "
                             "down to the 2 m box of the last row", width=1040)


def account_status():
    cols = [("DXCC", "Award"), ("New LoTW", "QSLs"), ("LoTW QSLs", "in Process"),
            ("DXCC Credits", "Awarded"), ("Total", "(All)"), ("Total", "(Current)")]
    widths = [96, 80, 90, 96, 70, 80]
    x0 = 260
    xs = [x0]
    for w in widths:
        xs.append(xs[-1] + w)
    width = xs[-1] - x0
    mid = lambda i: (xs[i] + xs[i + 1]) / 2          # noqa: E731
    rows = [("Mixed", 0, 2, 251), ("CW", 0, 1, 140), ("Phone", 1, 0, 132), ("Digital", 0, 3, 245),
            ("160M", 0, 0, 38), ("80M", 0, 1, 120), ("…", None, None, None), ("6M", 0, 0, 40),
            ("2M", 0, 0, 2), ("70CM", 0, 0, 0), ("Challenge", 0, 5, 1480)]
    body = [text(24, 28, "Account Status box (schematic, made-up data)", 13, MUTED)]
    y = 44
    body += [f'<rect x="{x0}" y="{y}" width="{width}" height="24" fill="{PANEL}" stroke="{LINE}"/>',
             text(x0 + 10, y + 16, "Account Status", 12, weight=600)]
    y += 24
    top = y
    body.append(f'<rect x="{x0}" y="{y}" width="{width}" height="40" fill="{PANEL}" stroke="{LINE}"/>')
    for i, (a, b) in enumerate(cols):
        body += [text(mid(i), y + 17, a, 10, MUTED, "middle", weight=600),
                 text(mid(i), y + 31, b, 10, MUTED, "middle", weight=600)]
    body += grid_lines(xs, y, 40)
    y += 40
    for name, new, proc, awarded in rows:
        body += [f'<rect x="{x0}" y="{y}" width="{width}" height="20" fill="{BG}" stroke="{LINE}"/>',
                 text(x0 + 8, y + 14, name, 11, MUTED if name == "…" else AMBER)]
        if new is not None:
            total = new + proc + awarded
            vals = [new, proc, awarded, "---" if name == "Challenge" else total, total]
            body += [text(mid(i + 1), y + 14, v, 10, anchor="middle", font=M) for i, v in enumerate(vals)]
        body += grid_lines(xs, y, 20)
        y += 20
    body.insert(1, f'<rect x="{x0}" y="{top}" width="{width}" height="{y - top}" fill="{SEL}"/>')
    body.append(text(x0 + width / 2, y + 20, "View Award Credit Matrix (that table is for Import)",
                     11, MUTED, "middle", extra=";text-decoration:underline"))
    body += marker(x0 - 12, top + 8, "Start: the DXCC Award heading", "end")
    body += marker(xs[-1] + 12, y - 10, "End: after the Challenge row")
    return svg(y + 40, body, "Copy the Account Status box from the DXCC Award heading "
                             "down to the Challenge row")


if __name__ == "__main__":
    (OUT / "copy_matrix.svg").write_text(matrix(), encoding="utf-8")
    (OUT / "copy_account_status.svg").write_text(account_status(), encoding="utf-8")
    print("wrote", OUT / "copy_matrix.svg", "and", OUT / "copy_account_status.svg")
