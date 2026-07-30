from __future__ import annotations

import argparse
from pathlib import Path

from app.db.database import SessionLocal
from app.services.vocabulary_import import DEFAULT_VOCABULARY_SOURCE_PATH, import_vocabulary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import demonstration vocabulary into the configured database.")
    parser.add_argument("--source", type=Path, default=DEFAULT_VOCABULARY_SOURCE_PATH)
    parser.add_argument("--update-existing", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as session:
        result = import_vocabulary(session, args.source, update_existing=args.update_existing)

    print(f"inserted={result.inserted} skipped={result.skipped} updated={result.updated}")


if __name__ == "__main__":
    main()
