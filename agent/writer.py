"""Artikel-Generator: erzeugt deutsche Artikel via Ollama oder Anthropic API."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger("ki_industriewende.writer")

SYSTEM_PROMPT = """\
Du bist der Chefredakteur von ki-industriewende.de, einer unabhängigen deutschen Plattform \
für die Analyse der KI-gestützten Transformation der deutschen Industrie.

Dein Publikum: Unternehmer, Fachkräfte, Ausbilder, Politikinteressierte und neugierige Bürger.

Schreibregeln:
- Sprache: IMMER Deutsch. Klar, präzise, zugänglich aber fachlich korrekt.
- Länge: 900–1400 Wörter.
- Struktur: Einleitung (Problem/Hook), 3–5 H2-Abschnitte, Schluss mit Handlungsempfehlung.
- Ton: sachlich, ausgewogen, faktenbasiert. Kein Clickbait, kein Marketing-Sprech.
- Fakten: Konkrete Zahlen, Studien und Quellen nennen (BMWi, BMBF, Fraunhofer, McKinsey, WEF, IAB etc.)
- Am Ende: "## Wichtigste Erkenntnisse" als Bullet-Liste (3–5 Punkte).
- Kein YAML-Frontmatter. Direkt mit H1 beginnen.
- Für Debattenartikel: Beide Seiten fair und ausgewogen darstellen.
"""

USER_PROMPT_TEMPLATE = """\
Schreibe einen neuen Artikel für ki-industriewende.de.

Rubrik: {rubrik_name}
Thema: {thema}
Datum: {datum}

Recherche-Kontext (nutze diese Fakten und Quellen):
{recherche}

Schreibe den vollständigen Artikel auf Deutsch. \
Beginne direkt mit der H1-Überschrift (# Titel). \
Kein Markdown-Codeblock drum herum.
"""


def build_prompt(rubrik_name: str, thema: str, recherche: str) -> tuple[str, str]:
    import datetime as dt
    datum = dt.date.today().strftime("%d. %B %Y").replace(
        "January","Januar").replace("February","Februar").replace("March","März"
        ).replace("April","April").replace("May","Mai").replace("June","Juni"
        ).replace("July","Juli").replace("August","August").replace("September","September"
        ).replace("October","Oktober").replace("November","November").replace("December","Dezember")
    user = USER_PROMPT_TEMPLATE.format(
        rubrik_name=rubrik_name, thema=thema, datum=datum, recherche=recherche[:3000]
    )
    return SYSTEM_PROMPT, user


def generate_with_ollama(rubrik_name: str, thema: str, recherche: str,
                          model: str = "qwen3.6:latest",
                          base_url: str = "http://localhost:11434/v1") -> str:
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key="ollama")
    system_prompt, user_prompt = build_prompt(rubrik_name, thema, recherche)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
    )
    return resp.choices[0].message.content.strip()


def generate_with_anthropic(rubrik_name: str, thema: str, recherche: str,
                             model: str | None = None) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    system_prompt, user_prompt = build_prompt(rubrik_name, thema, recherche)
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def extract_title(markdown: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "Ohne Titel"


def wrap_with_frontmatter(markdown: str, rubrik_name: str, thema: str, tags: list[str]) -> str:
    import datetime as dt
    title = extract_title(markdown)
    fm = {
        "title": title,
        "rubrik": rubrik_name,
        "thema": thema,
        "datum": dt.date.today().isoformat(),
        "sprache": "de",
        "tags": tags,
    }
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(json.dumps(x) for x in v)}]")
        else:
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + markdown.lstrip()
