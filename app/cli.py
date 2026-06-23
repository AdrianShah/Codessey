"""CLI fallback — python -m app.cli review <file>"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from app.review import review_paste
from agents.ingestion import IngestionError


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if len(sys.argv) < 3 or sys.argv[1] != "review":
        print("Usage: python -m app.cli review <file>")
        sys.exit(1)

    filepath = Path(sys.argv[2])
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8", errors="replace")
    try:
        report = asyncio.run(review_paste(content, filepath.name))
    except IngestionError as e:
        print(f"Ingestion error: {e}")
        sys.exit(1)

    print(report.markdown_report)


if __name__ == "__main__":
    main()
