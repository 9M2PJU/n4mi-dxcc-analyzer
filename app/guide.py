"""The in-app user guide (D58).

The Help page shows User_Guide.md itself, so the app and GitHub always show
the same guide and there is only one file to edit. It is rendered once at
start-up with Python-Markdown. The guide is our own file in the repository,
so its HTML is trusted, like the rest of the app's pages.

Differences from GitHub's view:
  * The guide's own "Contents" list is dropped; the Help page shows a
    contents panel built from the headings instead.
  * The title heading is dropped; the page header already says "User guide".
  * Image paths become /images/..., and the README link points to GitHub,
    because the README isn't inside the app.
  * Lists nest at 2 spaces, as on GitHub (Python-Markdown's default is 4,
    which ran the guide's sub-bullets into their numbered steps).

A missing or unreadable guide never stops the app: the Help page says so.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
GUIDE_PATH = ROOT / "User_Guide.md"
IMAGES_DIR = ROOT / "images"
README_URL = "https://github.com/N4MI73/n4mi-dxcc-analyzer#readme"


@dataclass
class Guide:
    html: str = ""
    toc: list = field(default_factory=list)   # [(id, name, [(id, name), ...]), ...]
    error: str | None = None


def _drop_contents(text):
    """Remove the '## Contents' section (up to the next '## ' heading)."""
    return re.sub(r"(?ms)^## Contents[ \t]*\n.*?(?=^## )", "", text, count=1)


def render(path=GUIDE_PATH):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Guide(error=f"The user guide couldn't be read ({Path(path).name}: {exc.__class__.__name__}).")
    md = markdown.Markdown(extensions=["toc", "tables", "md_in_html"], tab_length=2)
    body = md.convert(_drop_contents(text))
    body = re.sub(r"<h1[^>]*>.*?</h1>", "", body, count=1, flags=re.S)
    body = body.replace('href="README.md"', f'href="{README_URL}"')
    body = re.sub(r'src="(?:\./)?images/', 'src="/images/', body)
    tokens = md.toc_tokens
    if len(tokens) == 1 and tokens[0]["level"] == 1:   # the title: use its sections
        tokens = tokens[0]["children"]
    toc = [(t["id"], t["name"], [(c["id"], c["name"]) for c in t["children"]]) for t in tokens]
    return Guide(html=body, toc=toc)


def toc_html(guide):
    from html import escape
    items = []
    for sid, name, kids in guide.toc:
        sub = "".join(f'<li><a href="#{escape(k)}">{escape(n)}</a></li>' for k, n in kids)
        items.append(f'<li><a href="#{escape(sid)}">{escape(name)}</a>'
                     + (f"<ul>{sub}</ul>" if sub else "") + "</li>")
    return "<ul>" + "".join(items) + "</ul>"


def page(template, guide):
    """The Help page: the static template with the guide and contents filled in."""
    if guide.error:
        from html import escape
        body = (f'<div class="notice bad" role="alert"><div><div class="t">Guide not available</div>'
                f'<div>{escape(guide.error)} The guide is also on GitHub: '
                f'<a href="https://github.com/N4MI73/n4mi-dxcc-analyzer/blob/main/User_Guide.md">'
                f'User_Guide.md</a>.</div></div></div>')
        return template.replace("<!--TOC-->", "").replace("<!--GUIDE-->", body)
    return template.replace("<!--TOC-->", toc_html(guide)).replace("<!--GUIDE-->", guide.html)
