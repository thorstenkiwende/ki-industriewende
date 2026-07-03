"""Web-Recherche-Modul: sucht aktuelle Quellen zu einem Thema auf Deutsch."""

from __future__ import annotations
import logging
from typing import Any

log = logging.getLogger("ki_industriewende.researcher")

MAX_RESULTS = 8
FETCH_LIMIT  = 6000


def web_search(query: str, max_results: int = MAX_RESULTS) -> str:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region="de-de"))
        if not results:
            return f"Keine Ergebnisse für: {query}"
        lines = [f"Suchergebnisse für: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r.get('title', '–')}**")
            lines.append(f"   URL: {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Suchfehler: {e}"


def web_fetch(url: str) -> str:
    try:
        import httpx
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (compatible; KI-Industriewende-Bot/1.0)"}
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator="\n").split())
        return text[:FETCH_LIMIT] + ("…" if len(text) > FETCH_LIMIT else "")
    except Exception as e:
        return f"Fehler beim Abrufen von {url}: {e}"


def research_topic(thema: str, rubrik_name: str) -> str:
    """Führt mehrstufige Recherche zu einem Thema durch und gibt eine Zusammenfassung zurück."""
    log.info("Recherchiere: %s", thema)
    query_de = f"{thema} Deutschland 2025 2026"
    query_aktuell = f"{thema} aktuelle Studie Daten Statistik"

    results = []
    results.append(web_search(query_de))
    results.append(web_search(query_aktuell))
    results.append(web_search(f"{rubrik_name} KI Deutschland Trend"))

    return "\n\n---\n\n".join(results)


# OpenAI-kompatible Tool-Definitionen
RESEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Suche im Web nach aktuellen deutschen und internationalen Quellen zu einem Thema. "
                "Nutze dies um Fakten, Studien, Statistiken und aktuelle Entwicklungen zu finden. "
                "Suche bevorzugt auf Deutsch."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Die Suchanfrage. Konkret und spezifisch formulieren."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Anzahl der Ergebnisse (1-10). Standard: 8."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Ruft den Inhalt einer spezifischen URL ab. Nutze dies nach web_search, um detaillierte Informationen von einer Quelle zu lesen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Die vollständige URL der abzurufenden Seite."
                    }
                },
                "required": ["url"]
            }
        }
    }
]


def execute_research_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    if tool_name == "web_search":
        return web_search(tool_input["query"], tool_input.get("max_results", MAX_RESULTS))
    elif tool_name == "web_fetch":
        return web_fetch(tool_input["url"])
    return f"Unbekanntes Tool: {tool_name}"
