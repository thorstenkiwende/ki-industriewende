"""
KI-Industriewende Agent — Hauptsteuerung.

Verwendung:
  python main.py run                        # Nächstes Thema recherchieren + Artikel schreiben
  python main.py run --rubrik kmu           # Bestimmte Rubrik erzwingen
  python main.py run --thema "KI im Handwerk"  # Eigenes Thema vorgeben
  python main.py run --dry-run              # Nur Recherche, kein Artikel schreiben
  python main.py run --backend anthropic    # Anthropic statt Ollama nutzen
  python main.py research "Thema"          # Nur Recherche, keine Artikel
  python main.py list                      # Alle bisherigen Artikel anzeigen
  python main.py rebuild-index             # Blog-Index neu aufbauen
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

# Fix Windows console encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from researcher import research_topic
from writer import (
    generate_with_ollama, generate_with_anthropic,
    extract_title, wrap_with_frontmatter,
)
from site_builder import (
    build_article_page, update_blog_index,
    load_article_registry, save_article_registry,
    WEBSITE_DIR, _slugify,
)

log = logging.getLogger("ki_industriewende")

TOPICS_PATH = ROOT / "agent" / "topics.json"
STATE_PATH  = ROOT / "agent" / "state.json"
CONTENT_DIR = ROOT / "content"


def load_topics() -> dict:
    return json.loads(TOPICS_PATH.read_text(encoding="utf-8"))


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def pick_next(topics: dict, state: dict, forced_rubrik: str | None = None) -> tuple[dict, str]:
    rubriken = topics["rubriken"]
    if forced_rubrik:
        rubrik = next((r for r in rubriken if r["id"] == forced_rubrik), None)
        if not rubrik:
            raise ValueError(f"Unbekannte Rubrik: {forced_rubrik}. Verfügbar: {[r['id'] for r in rubriken]}")
        rubrik_idx = rubriken.index(rubrik)
    else:
        rubrik_idx = (state["last_rubrik_index"] + 1) % len(rubriken)
        rubrik = rubriken[rubrik_idx]

    themen = rubrik["seed_themen"]
    last_idx = state["last_thema_index"].get(rubrik["id"], -1)
    thema_idx = (last_idx + 1) % len(themen)
    thema = themen[thema_idx]

    state["last_rubrik_index"] = rubrik_idx
    state["last_thema_index"][rubrik["id"]] = thema_idx
    return rubrik, thema


def cmd_run(args: argparse.Namespace) -> int:
    topics = load_topics()
    state  = load_state()

    # Rubrik & Thema bestimmen
    if args.thema:
        rubrik_id = args.rubrik or "debatte"
        rubrik = next((r for r in topics["rubriken"] if r["id"] == rubrik_id), topics["rubriken"][0])
        thema  = args.thema
    else:
        rubrik, thema = pick_next(topics, state, args.rubrik)

    log.info("Rubrik: %s | Thema: %s", rubrik["name"], thema)
    print(f"\n📚 Rubrik:  {rubrik['name']}")
    print(f"📌 Thema:   {thema}")

    # Recherche
    print("\n🔍 Recherche läuft...")
    recherche = research_topic(thema, rubrik["name"])
    print(f"   ✓ {len(recherche)} Zeichen Recherche-Material gesammelt")

    if args.dry_run:
        print("\n[Dry-Run] Recherche abgeschlossen. Kein Artikel geschrieben.")
        print("\n--- RECHERCHE-VORSCHAU ---")
        print(recherche[:1500])
        return 0

    # Artikel generieren
    print(f"\n✍️  Artikel wird generiert ({args.backend})...")
    try:
        if args.backend == "anthropic":
            body_md = generate_with_anthropic(rubrik["name"], thema, recherche)
        else:
            model    = args.model or "qwen3.6:latest"
            base_url = args.ollama_url or "http://localhost:11434/v1"
            body_md  = generate_with_ollama(rubrik["name"], thema, recherche, model, base_url)
    except Exception as e:
        log.exception("Fehler bei der Artikel-Generierung: %s", e)
        return 1

    title = extract_title(body_md)
    print(f"   ✓ Artikel: „{title}“")

    # Markdown mit Frontmatter speichern
    md_full = wrap_with_frontmatter(
        body_md,
        rubrik_name=rubrik["name"],
        thema=thema,
        tags=["KI", "Deutschland", rubrik["name"]],
    )
    today     = dt.date.today().isoformat()
    slug      = _slugify(title)[:60]
    md_path   = CONTENT_DIR / rubrik["output_dir"] / f"{today}-{slug}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_full, encoding="utf-8")
    print(f"\n💾 Markdown: {md_path.relative_to(ROOT)}")

    # HTML-Artikel-Seite bauen
    articles_subdir = WEBSITE_DIR / rubrik["output_dir"] / "artikel"
    html_path = articles_subdir / f"{today}-{slug}.html"
    meta = build_article_page(md_full, rubrik["id"], html_path)
    print(f"🌐 HTML:     website/{rubrik['output_dir']}/artikel/{today}-{slug}.html")

    # Artikel-Registry aktualisieren
    registry = load_article_registry()
    registry = [a for a in registry if a.get("html_path") != meta["html_path"]]
    registry.append(meta)
    save_article_registry(registry)

    # Blog-Index aktualisieren
    update_blog_index(registry)
    print("📰 Blog-Index aktualisiert")

    # State speichern
    state.setdefault("history", []).append({
        "utc":      dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "rubrik":   rubrik["id"],
        "thema":    thema,
        "titel":    title,
        "markdown": str(md_path.relative_to(ROOT)),
        "html":     meta["html_path"],
    })
    state["history"]    = state["history"][-100:]
    state["last_run_utc"] = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_state(state)

    print(f"\n✅ Fertig! Artikel gespeichert und Website aktualisiert.")
    return 0


def cmd_research(args: argparse.Namespace) -> int:
    thema    = args.thema_text
    rubrik   = args.rubrik or "allgemein"
    print(f"\n🔍 Recherche zu: {thema}")
    ergebnis = research_topic(thema, rubrik)
    print(ergebnis)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    registry = load_article_registry()
    if not registry:
        print("Noch keine Artikel generiert.")
        return 0
    print(f"\n📋 {len(registry)} Artikel:\n")
    for a in sorted(registry, key=lambda x: x.get("datum",""), reverse=True):
        print(f"  [{a['datum']}] {a['rubrik_label']:20s} {a['title']}")
    return 0


def cmd_rebuild_index(args: argparse.Namespace) -> int:
    registry = load_article_registry()
    update_blog_index(registry)
    print(f"✅ Blog-Index neu aufgebaut mit {len(registry)} Artikeln.")
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="KI-Industriewende Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd")

    # run
    run_p = sub.add_parser("run", help="Thema recherchieren und Artikel schreiben")
    run_p.add_argument("--rubrik", choices=["industrie","wissenschaft","debatte","ausbildung","kmu"],
                       help="Rubrik erzwingen")
    run_p.add_argument("--thema", help="Eigenes Thema vorgeben")
    run_p.add_argument("--dry-run", action="store_true", help="Nur Recherche, kein Artikel")
    run_p.add_argument("--backend", choices=["ollama","anthropic"], default="ollama")
    run_p.add_argument("--model", help="Ollama-Modellname (Standard: qwen3.6:latest)")
    run_p.add_argument("--ollama-url", help="Ollama-URL (Standard: http://localhost:11434/v1)")

    # research
    res_p = sub.add_parser("research", help="Nur Recherche ohne Artikel-Generierung")
    res_p.add_argument("thema_text", help="Das zu recherchierende Thema")
    res_p.add_argument("--rubrik", help="Rubrik-Kontext")

    # list
    sub.add_parser("list", help="Alle generierten Artikel anzeigen")

    # rebuild-index
    sub.add_parser("rebuild-index", help="Blog-Index aus Registry neu aufbauen")

    ap.add_argument("-v", "--verbose", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.cmd == "run":
        return cmd_run(args)
    elif args.cmd == "research":
        return cmd_research(args)
    elif args.cmd == "list":
        return cmd_list(args)
    elif args.cmd == "rebuild-index":
        return cmd_rebuild_index(args)
    else:
        print(__doc__)
        return 0


if __name__ == "__main__":
    sys.exit(main())
