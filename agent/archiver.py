"""Archiviert die gebaute Website (docs/) als datierten GitHub Release.

Erfordert eine authentifizierte GitHub CLI (`gh auth login`). Ein Fehlschlag
(z. B. weil `gh` nicht installiert oder nicht eingeloggt ist) wird nur
geloggt — der Pipeline-Lauf selbst bricht dadurch nicht ab.
"""

from __future__ import annotations

import datetime as dt
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("ki_industriewende.archiver")

ROOT = Path(__file__).resolve().parents[1]
WEBSITE_DIR = ROOT / "docs"


def archive_site() -> str | None:
    """Zippt docs/ und veröffentlicht es als GitHub Release. Gibt den Tag-Namen zurück, oder None bei Fehlschlag."""
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    tag = f"site-{timestamp}"

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(shutil.make_archive(str(Path(tmp) / tag), "zip", root_dir=WEBSITE_DIR))
        try:
            subprocess.run(
                [
                    "gh", "release", "create", tag, str(zip_path),
                    "--title", f"Website-Snapshot {timestamp}",
                    "--notes", f"Automatisches Archiv von docs/ nach Pipeline-Lauf am {timestamp}.",
                ],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
        except FileNotFoundError:
            log.warning("Archivierung übersprungen: GitHub CLI (gh) nicht gefunden.")
            return None
        except subprocess.CalledProcessError as e:
            log.warning("Archivierung fehlgeschlagen (gh release create): %s", e.stderr.strip())
            return None

    log.info("Archiv veröffentlicht: Release %s", tag)
    return tag
