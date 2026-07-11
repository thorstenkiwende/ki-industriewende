"""Site-Builder: wandelt Markdown-Artikel in HTML-Seiten um und aktualisiert den Blog-Index."""

from __future__ import annotations

import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown as _md_lib

log = logging.getLogger("ki_industriewende.site_builder")

ROOT = Path(__file__).resolve().parents[1]
WEBSITE_DIR = ROOT / "docs"

RUBRIK_META = {
    "industrie":    {"label": "Industrie 4.0",       "color": "#dbeafe", "tag_class": "blue",  "emoji": "🏭"},
    "wissenschaft": {"label": "Wissenschaft & KI",   "color": "#dcfce7", "tag_class": "teal",  "emoji": "🔬"},
    "debatte":      {"label": "KI-Debatte",           "color": "#fef9c3", "tag_class": "red",   "emoji": "⚖️"},
    "ausbildung":   {"label": "Ausbildung",           "color": "#fce7f3", "tag_class": "teal",  "emoji": "🎓"},
    "kmu":          {"label": "KMU & Mittelstand",    "color": "#ede9fe", "tag_class": "",      "emoji": "💼"},
}

_ARTICLE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} – KI-Industriewende</title>
  <meta name="description" content="{excerpt}">
  <link rel="stylesheet" href="../../assets/css/style.css">
</head>
<body>
<nav class="nav">
  <div class="container nav-inner">
    <a href="../../index.html" class="nav-logo"><span class="logo-ki">KI</span>Industriewende</a>
    <ul class="nav-links">
      <li><a href="../../index.html">Start</a></li>
      <li><a href="../../industrie/index.html">Industrie 4.0</a></li>
      <li><a href="../../wissenschaft/index.html">Wissenschaft & KI</a></li>
      <li><a href="../../ausbildung/index.html">Ausbildung</a></li>
      <li><a href="../../kmu/index.html">KMU</a></li>
      <li><a href="../../blog/index.html" class="nav-cta">Blog</a></li>
    </ul>
  </div>
</nav>
<div class="container">
  <div class="breadcrumb">
    <a href="../../index.html">Start</a>
    <span>›</span>
    <a href="../../blog/index.html">Blog</a>
    <span>›</span>
    <a href="../../{rubrik_id}/index.html">{rubrik_label}</a>
    <span>›</span>
    <span>{title}</span>
  </div>
</div>
<article class="article-page">
  <span class="tag {tag_class}">{rubrik_label}</span>
  <h1>{title}</h1>
  <div class="article-meta-bar">
    <span>📅 {datum}</span>
    <span>🏷️ {rubrik_label}</span>
    <span>🤖 KI-recherchiert</span>
  </div>
  {body}
</article>
<section class="cta-section section-sm">
  <div class="container">
    <div class="cta-box">
      <h2>Weitere Beiträge entdecken</h2>
      <p>Wöchentlich neue Analysen zur KI-Industriewende Deutschlands.</p>
      <div class="cta-btns">
        <a href="../../blog/index.html" class="btn btn-primary">Alle Beiträge</a>
        <a href="../../{rubrik_id}/index.html" class="btn btn-outline">Mehr {rubrik_label}</a>
      </div>
    </div>
  </div>
</section>
<footer class="footer">
  <div class="container">
    <div class="footer-bottom">
      <span>© 2026 KI-Industriewende</span>
      <span><a href="../../index.html#datenschutz">Datenschutz</a> · <a href="../../index.html#impressum">Impressum</a></span>
    </div>
  </div>
</footer>
</body>
</html>"""


_MONATE_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _format_datum_lang(value: str) -> str:
    """Wandelt ein gespeichertes Datum in das lange deutsche Format um (z. B. '11. Juli 2026').

    Akzeptiert ISO (YYYY-MM-DD) und DD.MM.YYYY; bei Fehlschlag wird der Originalwert
    zurückgegeben. Die Registry speichert weiterhin ISO, damit die Sortierung stimmt.
    """
    s = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            d = datetime.strptime(s[:10], fmt)
            return f"{d.day}. {_MONATE_DE[d.month - 1]} {d.year}"
        except ValueError:
            continue
    return s


def _md_to_html_body(md_content: str) -> str:
    return _md_lib.markdown(
        md_content,
        extensions=["tables", "fenced_code", "nl2br", "toc"],
        output_format="html5",
    )


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[äöüß]", lambda m: {"ä":"ae","ö":"oe","ü":"ue","ß":"ss"}[m.group()], text)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "artikel"


def _extract_excerpt(md_body: str, max_len: int = 180) -> str:
    for para in re.split(r"\n\n+", md_body):
        p = para.strip()
        if p and not p.startswith("#"):
            clean = re.sub(r"[*_`#\[\]]", "", p)
            return re.sub(r"\s+", " ", clean)[:max_len].rstrip() + "…"
    return ""


def build_article_page(md_with_frontmatter: str, rubrik_id: str, output_path: Path) -> dict:
    """Wandelt einen Markdown-Artikel in eine HTML-Seite um. Gibt Metadaten zurück."""
    # Strip frontmatter
    body_md = re.sub(r"^---\n.*?\n---\n", "", md_with_frontmatter, count=1, flags=re.DOTALL)

    # Extract title
    title = "Artikel"
    for line in body_md.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break

    # Extract frontmatter fields
    fm_match = re.match(r"^---\n(.*?)\n---\n", md_with_frontmatter, re.DOTALL)
    datum = datetime.now().strftime("%d.%m.%Y")
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if line.startswith("datum:"):
                datum = line.split(":", 1)[1].strip().strip('"')

    meta = RUBRIK_META.get(rubrik_id, {"label": rubrik_id, "color": "#f1f5f9", "tag_class": "", "emoji": "📄"})
    excerpt = _extract_excerpt(body_md)
    body_html = _md_to_html_body(body_md)

    html = _ARTICLE_TEMPLATE.format(
        title=title,
        excerpt=excerpt,
        body=body_html,
        rubrik_id=rubrik_id,
        rubrik_label=meta["label"],
        tag_class=meta["tag_class"],
        datum=_format_datum_lang(datum),  # Anzeige lang; Registry behält ISO
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    log.info("Artikel gespeichert: %s", output_path)

    return {
        "title": title,
        "excerpt": excerpt,
        "rubrik_id": rubrik_id,
        "rubrik_label": meta["label"],
        "rubrik_emoji": meta["emoji"],
        "tag_class": meta["tag_class"],
        "rubrik_color": meta["color"],
        "datum": datum,
        "html_path": str(output_path.relative_to(WEBSITE_DIR)),
    }


# Marker, die die injizierte Artikelliste im Blog-Index begrenzen. Explizite
# Marker (statt Matching auf das umschließende <div>...</div>) verhindern das
# Fehlmatchen auf das erste verschachtelte </div> innerhalb eines Artikel-Items.
_LIST_START = "<!-- ARTICLES:START -->"
_LIST_END = "<!-- ARTICLES:END -->"


def update_blog_index(articles: list[dict]) -> None:
    """Aktualisiert den Blog-Index mit allen bekannten Artikeln (neueste zuerst)."""
    index_path = WEBSITE_DIR / "blog" / "index.html"
    if not index_path.exists():
        log.warning("Blog-Index nicht gefunden: %s", index_path)
        return

    # Build article list HTML
    items_html = []
    for a in sorted(articles, key=lambda x: x.get("datum", ""), reverse=True):
        rel_path = a["html_path"].replace("\\", "/")
        items_html.append(f"""\
      <a href="../{rel_path}" class="article-item">
        <div class="article-emoji">{a['rubrik_emoji']}</div>
        <div>
          <div class="article-meta">{a['rubrik_label']} · {_format_datum_lang(a['datum'])}</div>
          <h3>{a['title']}</h3>
          <p>{a['excerpt']}</p>
        </div>
      </a>""")

    new_list = "\n".join(items_html) if items_html else "      <p>Noch keine Artikel vorhanden.</p>"

    content = index_path.read_text(encoding="utf-8")
    start = content.find(_LIST_START)
    end = content.find(_LIST_END)
    if start == -1 or end == -1 or end < start:
        log.warning("Artikel-Marker nicht gefunden in %s — Index nicht aktualisiert", index_path)
        return
    new_content = (
        content[: start + len(_LIST_START)]
        + "\n" + new_list + "\n      "
        + content[end:]
    )
    index_path.write_text(new_content, encoding="utf-8")
    log.info("Blog-Index aktualisiert mit %d Artikeln", len(articles))


def load_article_registry() -> list[dict]:
    registry_path = ROOT / "agent" / "article_registry.json"
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding="utf-8"))
    return []


def save_article_registry(articles: list[dict]) -> None:
    registry_path = ROOT / "agent" / "article_registry.json"
    registry_path.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
