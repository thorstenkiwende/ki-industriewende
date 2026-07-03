# KI-Industriewende

**Ein autonomer Publishing-Agent, der recherchierte deutschsprachige Artikel über die KI-Transformation der deutschen Industrie schreibt und als statische Website veröffentlicht.**

Der Agent wählt zyklisch ein Thema aus einem Themenkatalog, recherchiert dazu im Web, lässt einen Artikel von einem LLM (Ollama lokal oder Anthropic Claude) generieren, speichert ihn als Markdown und baut daraus eine fertige HTML-Seite samt aktualisiertem Blog-Index. Das Ergebnis ist eine GitHub-Pages-taugliche Website unter der Domain [ki-industriewende.de](https://ki-industriewende.de).

---

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Funktionsweise (Pipeline)](#funktionsweise-pipeline)
- [Projektstruktur](#projektstruktur)
- [Installation](#installation)
- [Verwendung (CLI)](#verwendung-cli)
- [Themenkatalog & Rubriken](#themenkatalog--rubriken)
- [Module im Detail](#module-im-detail)
- [Zustand & Datenhaltung](#zustand--datenhaltung)
- [Website & Deployment](#website--deployment)
- [Konfiguration](#konfiguration)

---

## Überblick

| | |
|---|---|
| **Zweck** | Automatisierte redaktionelle Content-Produktion zur KI-Industriewende Deutschlands |
| **Sprache der Inhalte** | Deutsch |
| **LLM-Backends** | Ollama (lokal, Standard) oder Anthropic Claude |
| **Recherche** | Web-Suche via DuckDuckGo (`ddgs`), optional Seiten-Abruf via `httpx` + BeautifulSoup |
| **Ausgabe** | Markdown (`content/`) + statisches HTML (`docs/`) |
| **Hosting** | GitHub Pages (`docs/`-Verzeichnis), Custom-Domain via `CNAME` |
| **Steuerung** | CLI (`python main.py …`) |

Der Agent ist als klassische, mehrstufige Pipeline aufgebaut: **Themenwahl → Recherche → Artikel-Generierung → Markdown-Speicherung → HTML-Build → Index-Update → Zustands-Speicherung.**

---

## Funktionsweise (Pipeline)

```
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
│ topics.json│──▶│ researcher │──▶│   writer   │──▶│site_builder│
│  + state   │   │ (Web-Suche)│   │(LLM-Artikel)│   │(HTML+Index)│
└────────────┘   └────────────┘   └────────────┘   └────────────┘
      │                                                    │
   Rubrik &                                          content/*.md
   Thema wählen                                      docs/**/*.html
                                                     state.json,
                                                     article_registry.json
```

1. **Themenwahl** (`main.pick_next`) — Aus `topics.json` wird auf Basis von `state.json` die nächste Rubrik (Round-Robin) und das nächste Seed-Thema innerhalb der Rubrik gewählt. Rubrik oder Thema lassen sich per CLI-Flag erzwingen.
2. **Recherche** (`researcher.research_topic`) — Mehrere deutschsprachige Web-Suchen (Thema, aktuelle Studien/Statistiken, Rubrik-Trend) werden zu einem Recherche-Block zusammengefasst.
3. **Artikel-Generierung** (`writer`) — System- und User-Prompt werden gebaut; das gewählte Backend erzeugt einen 900–1400-Wörter-Artikel in Markdown, direkt beginnend mit H1.
4. **Speicherung** — Der Artikel wird mit YAML-Frontmatter versehen und unter `content/<rubrik>/JJJJ-MM-TT-<slug>.md` abgelegt.
5. **HTML-Build** (`site_builder.build_article_page`) — Markdown wird in eine vollständige HTML-Seite mit Navigation, Breadcrumb, Meta-Leiste und CTA-Sektion gerendert.
6. **Index-Update** (`site_builder.update_blog_index`) — Die Artikel-Registry wird aktualisiert und der Blog-Index (`docs/blog/index.html`) neu befüllt.
7. **Zustands-Speicherung** — `state.json` erhält den neuen Rubrik-/Thema-Index sowie einen History-Eintrag (letzte 100 Läufe).

---

## Projektstruktur

```
agt_ki_industriewende/
├── agent/                     # Python-Quellcode des Agenten
│   ├── main.py                # CLI-Einstiegspunkt & Pipeline-Steuerung
│   ├── researcher.py          # Web-Recherche (Suche + Seiten-Abruf)
│   ├── writer.py              # LLM-Artikelgenerierung (Ollama / Anthropic)
│   ├── site_builder.py        # Markdown→HTML, Blog-Index, Registry
│   ├── topics.json            # Themenkatalog (5 Rubriken mit Seed-Themen)
│   ├── state.json             # Laufzeit-Zustand & Verlauf
│   └── article_registry.json  # Metadaten aller generierten Artikel
├── content/                   # Generierte Artikel als Markdown (Quelle)
│   ├── industrie/  ├── wissenschaft/  ├── debatte/
│   ├── ausbildung/ └── kmu/
├── docs/                      # Statische Website (GitHub-Pages-Root)
│   ├── index.html             # Startseite
│   ├── blog/index.html        # Blog-Übersicht (dynamisch befüllt)
│   ├── <rubrik>/index.html    # Rubrik-Übersichtsseiten
│   ├── <rubrik>/artikel/*.html# Generierte Artikel-Seiten
│   ├── assets/css/style.css   # Styling
│   ├── _config.yml            # Jekyll/GitHub-Pages-Konfiguration
│   └── CNAME                  # Custom-Domain: ki-industriewende.de
├── requirements.txt           # Python-Abhängigkeiten
└── .gitignore
```

---

## Installation

Voraussetzung: **Python 3.11+** (der Code nutzt moderne Typannotationen; kompiliert wurde er zuletzt mit CPython 3.14).

```bash
cd agt_ki_industriewende
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

**Abhängigkeiten** (`requirements.txt`):

| Paket | Zweck |
|---|---|
| `openai` | OpenAI-kompatibler Client für Ollama |
| `ddgs` | DuckDuckGo-Web-Suche |
| `httpx` | HTTP-Abruf von Quellseiten |
| `beautifulsoup4`, `lxml` | HTML-Parsing der Quellen |
| `markdown` | Markdown→HTML-Rendering |
| `anthropic` | Anthropic-Claude-Backend |
| `python-dotenv` | Laden von `.env` |
| `rich` | Formatierte Konsolenausgabe |

### Backend-Voraussetzungen

- **Ollama (Standard):** Lokale Ollama-Instanz unter `http://localhost:11434/v1`, Standardmodell `qwen3.6:latest`.
- **Anthropic:** Umgebungsvariable `ANTHROPIC_API_KEY` setzen; optional `ANTHROPIC_MODEL` (Standard `claude-sonnet-4-6`).

---

## Verwendung (CLI)

Alle Kommandos werden aus dem Verzeichnis `agent/` bzw. mit Pfad zu `main.py` ausgeführt:

```bash
# Nächstes Thema (Round-Robin) recherchieren + Artikel schreiben
python main.py run

# Bestimmte Rubrik erzwingen
python main.py run --rubrik kmu

# Eigenes Thema vorgeben
python main.py run --thema "KI im Handwerk"

# Nur Recherche, kein Artikel (Vorschau)
python main.py run --dry-run

# Anthropic statt Ollama nutzen
python main.py run --backend anthropic

# Ollama-Modell / URL überschreiben
python main.py run --model llama3:latest --ollama-url http://localhost:11434/v1

# Nur Recherche zu freiem Thema ausgeben
python main.py research "KI in der Logistik"

# Alle bisher generierten Artikel auflisten
python main.py list

# Blog-Index aus der Registry neu aufbauen
python main.py rebuild-index
```

### `run`-Optionen

| Flag | Beschreibung | Standard |
|---|---|---|
| `--rubrik {industrie,wissenschaft,debatte,ausbildung,kmu}` | Rubrik erzwingen | Round-Robin |
| `--thema "<Text>"` | Eigenes Thema vorgeben | Seed aus `topics.json` |
| `--dry-run` | Nur Recherche, kein Artikel | aus |
| `--backend {ollama,anthropic}` | LLM-Backend | `ollama` |
| `--model <name>` | Ollama-Modellname | `qwen3.6:latest` |
| `--ollama-url <url>` | Ollama-Endpoint | `http://localhost:11434/v1` |
| `-v, --verbose` | Debug-Logging | aus |

---

## Themenkatalog & Rubriken

Der Themenkatalog liegt in `agent/topics.json`. Jede Rubrik hat eine ID, Beschreibung, ein Ausgabeverzeichnis und eine Liste von **Seed-Themen**, die zyklisch abgearbeitet werden.

| ID | Rubrik | Emoji | Fokus |
|---|---|---|---|
| `industrie` | Industrie 4.0 | 🏭 | Smart Factory, Predictive Maintenance, Robotik |
| `wissenschaft` | Wissenschaft & KI | 🔬 | Forschung, Ethik, LLMs, EU AI Act |
| `debatte` | KI-Debatte | ⚖️ | Pro & Contra, Zukunft der Arbeit |
| `ausbildung` | Ausbildung & Qualifikation | 🎓 | Berufsausbildung, Weiterbildung, Hochschule |
| `kmu` | KMU & Mittelstand | 💼 | KI-Einführung, Förderung, Praxisbeispiele |

Jede Rubrik enthält 8 Seed-Themen. Neue Rubriken oder Themen lassen sich durch Bearbeiten von `topics.json` ergänzen — die Round-Robin-Logik passt sich automatisch an.

---

## Module im Detail

### `main.py` — Steuerung & CLI
Einstiegspunkt. Enthält das Argument-Parsing, die Themenwahl (`pick_next`, Round-Robin über Rubriken und Themen) und die vollständige Pipeline (`cmd_run`). Behebt außerdem die Windows-Konsolen-Kodierung (UTF-8). Weitere Kommandos: `research`, `list`, `rebuild-index`.

### `researcher.py` — Web-Recherche
- `web_search(query)` — DuckDuckGo-Suche (`ddgs`), Region `de-de`, formatiert bis zu 8 Ergebnisse.
- `web_fetch(url)` — Ruft eine Seite ab, entfernt Skripte/Navigation/Footer und liefert bis zu 6000 Zeichen Klartext.
- `research_topic(thema, rubrik)` — Kombiniert mehrere Suchanfragen zu einem Recherche-Block.
- Zusätzlich sind OpenAI-kompatible **Tool-Definitionen** (`RESEARCH_TOOLS`) und ein Dispatcher (`execute_research_tool`) enthalten — für agentische Tool-Use-Szenarien.

### `writer.py` — Artikel-Generierung
- `SYSTEM_PROMPT` — Definiert die Redaktionsrolle: Deutsch, 900–1400 Wörter, feste Struktur (Einleitung, 3–5 H2, Abschluss mit „## Wichtigste Erkenntnisse"), sachlich-ausgewogener Ton, konkrete Quellen.
- `generate_with_ollama(...)` — Generierung über lokalen Ollama-Server (OpenAI-Client).
- `generate_with_anthropic(...)` — Generierung über die Anthropic-API.
- `extract_title(...)` — Liest die H1 als Titel.
- `wrap_with_frontmatter(...)` — Fügt YAML-Frontmatter (Titel, Rubrik, Thema, Datum, Sprache, Tags) hinzu.

### `site_builder.py` — HTML-Build & Index
- `build_article_page(...)` — Rendert Markdown zu einer vollständigen HTML-Artikelseite (Template mit Navigation, Breadcrumb, Meta-Leiste, CTA, Footer) und liefert Metadaten zurück.
- `update_blog_index(...)` — Ersetzt den Inhalt der `<div id="article-list">` im Blog-Index mit allen Artikeln (neueste zuerst).
- `_slugify(...)` — Erzeugt URL-taugliche Slugs inkl. Umlaut-Transliteration (ä→ae usw.).
- `load/save_article_registry(...)` — Verwalten von `article_registry.json`.
- `RUBRIK_META` — Farb-, Emoji- und Label-Zuordnung pro Rubrik.

---

## Zustand & Datenhaltung

| Datei | Inhalt |
|---|---|
| `agent/state.json` | Aktueller Rubrik-/Thema-Index (Round-Robin-Position), letzter Lauf (UTC), Verlauf der letzten 100 Läufe |
| `agent/article_registry.json` | Metadaten aller generierten Artikel (Titel, Excerpt, Rubrik, Datum, HTML-Pfad) — Quelle für den Blog-Index |
| `content/<rubrik>/*.md` | Generierte Artikel als Markdown mit Frontmatter (Quellformat) |
| `docs/<rubrik>/artikel/*.html` | Gerenderte HTML-Artikelseiten (Publikationsformat) |

`state.json` und `article_registry.json` werden standardmäßig **mitversioniert** (die entsprechenden Zeilen in `.gitignore` sind auskommentiert), damit der Round-Robin-Zustand über Läufe hinweg erhalten bleibt.

---

## Website & Deployment

- Die Website wird aus dem Verzeichnis **`docs/`** ausgeliefert — das Standard-Quellverzeichnis für **GitHub Pages**.
- `docs/CNAME` bindet die Custom-Domain **ki-industriewende.de**.
- `docs/_config.yml` setzt Titel, Beschreibung und URL (Jekyll-Theme deaktiviert, reines statisches HTML/CSS).
- Neue Artikel erscheinen automatisch im Blog-Index (`docs/blog/index.html`) sowie unter der jeweiligen Rubrik.

**Publishing-Ablauf:** `python main.py run` → Dateien in `content/` und `docs/` werden erzeugt/aktualisiert → committen und pushen → GitHub Pages liefert die aktualisierte Seite aus.

---

## Konfiguration

| Variable / Datei | Zweck |
|---|---|
| `ANTHROPIC_API_KEY` (env) | API-Schlüssel für das Anthropic-Backend |
| `ANTHROPIC_MODEL` (env) | Claude-Modell (Standard `claude-sonnet-4-6`) |
| `.env` | Wird über `python-dotenv` geladen (nicht versioniert) |
| `agent/topics.json` | Rubriken & Seed-Themen |
| `docs/_config.yml`, `docs/CNAME` | Website-Metadaten & Domain |

---

*Autonomer Redaktionsagent zur KI-Industriewende Deutschlands. Inhalte sind KI-recherchiert und -generiert.*
