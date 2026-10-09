#!/usr/bin/env python3
"""Read-only local API search/get/stats. Queries never execute provider APIs."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import sys
import tempfile
import json
from pathlib import Path
import re
import sqlite3
import unicodedata

DEFAULT_DB = Path(__file__).resolve().parent / "dist/catalog.sqlite"


def connect(path=DEFAULT_DB):
    if Path(path).resolve() == DEFAULT_DB.resolve():
        ensure_database()
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.create_function("catalog_fold", 1, fold_text, deterministic=True)
    return conn


def fold_text(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))


def search(conn, query="", provider=None, category=None, flag=None, limit=10, offset=0, force_like=False):
    limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)[:32]
    params, conditions = [], []
    if query.strip() and not tokens:
        conditions.append("0")
    for column, value in (("provider", provider),):
        if value:
            conditions.append(f"e.{column} = ?"); params.append(value)
    if category:
        conditions.append("EXISTS (SELECT 1 FROM category_memberships c WHERE c.entry_id=e.id AND c.category=?)"); params.append(category)
    if flag:
        conditions.append("EXISTS (SELECT 1 FROM entry_flags f WHERE f.entry_id=e.id AND f.flag=?)"); params.append(flag)
    fts_available = conn.execute("SELECT value FROM metadata WHERE key='fts5'").fetchone()
    use_fts = bool(tokens and not force_like and fts_available and json.loads(fts_available[0]))
    join, order = "", "e.name COLLATE NOCASE,e.id"
    if use_fts:
        join = " JOIN entries_fts ON entries_fts.id=e.id"
        conditions.append("entries_fts MATCH ?")
        params.append(" AND ".join('"' + token.replace('"', '""') + '"' for token in tokens))
        order = "bm25(entries_fts,0,5,1,2),e.id"
    else:
        for token in tokens:
            conditions.append("catalog_fold(e.name || ' ' || e.description || ' ' || e.search_text) LIKE ? ESCAPE '\\'")
            params.append("%" + fold_text(token).replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    try:
        total = conn.execute("SELECT count(*) FROM entries e" + join + where, params).fetchone()[0]
        rows = conn.execute("SELECT e.document FROM entries e" + join + where + " ORDER BY " + order + " LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    except sqlite3.OperationalError as exc:
        if use_fts and ("no such module: fts5" in str(exc) or "no such table: entries_fts" in str(exc)):
            return search(conn, query, provider, category, flag, limit, offset, force_like=True)
        raise
    return {"query": query, "total": total, "limit": limit, "offset": offset, "engine": "fts5" if use_fts else "like", "entries": [json.loads(row[0]) for row in rows]}


def get(conn, identifier):
    row = conn.execute("SELECT document FROM entries WHERE id=? OR canonical_url=?", (identifier, identifier)).fetchone()
    return json.loads(row[0]) if row else None


def stats(conn):
    return json.loads(conn.execute("SELECT value FROM metadata WHERE key='stats'").fetchone()[0])


def ensure_database():
    """Build the ignored local SQLite cache from the bundled archive, offline."""
    if DEFAULT_DB.exists():
        return
    from build_catalog import build_sqlite
    directory = DEFAULT_DB.parent
    manifest = json.loads((directory / "artifact-manifest.json").read_text(encoding="utf-8"))
    archive = (directory / "catalog.json.gz").read_bytes()
    expected = manifest["artifacts"]["catalog.json.gz"]["sha256"]
    if hashlib.sha256(archive).hexdigest() != expected:
        raise ValueError("Bundled catalog archive hash mismatch")
    with gzip.open(directory / "catalog.json.gz", "rb") as stream:
        payload = stream.read(64 * 1024 * 1024 + 1)
    if len(payload) > 64 * 1024 * 1024:
        raise ValueError("Catalog exceeds the supported 64 MiB bound")
    if hashlib.sha256(payload).hexdigest() != manifest["artifacts"]["catalog.json"]["sha256"]:
        raise ValueError("Catalog content hash mismatch")
    data = json.loads(payload)
    statistics = json.loads((directory / "stats.json").read_text(encoding="utf-8"))
    print("Building the local API search cache from the bundled archive...", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix=".catalog-bootstrap-", dir=directory) as temporary:
        path = Path(temporary) / "catalog.sqlite"
        build_sqlite(path, data, statistics)
        path.replace(DEFAULT_DB)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--json", action="store_true", help="JSON is the default; accepted for explicit automation")
    sub = parser.add_subparsers(dest="command", required=True)
    find = sub.add_parser("search")
    find.add_argument("query", nargs="?", default="")
    find.add_argument("--provider")
    find.add_argument("--category")
    find.add_argument("--flag")
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--offset", type=int, default=0)
    find.add_argument("--like", action="store_true", help="Use the parameterized LIKE fallback")
    find.add_argument("--json", action="store_true")
    detail = sub.add_parser("get")
    detail.add_argument("identifier")
    detail.add_argument("--json", action="store_true")
    report = sub.add_parser("stats")
    report.add_argument("--json", action="store_true")
    args = parser.parse_args()
    with connect(args.db) as conn:
        if args.command == "search":
            result = search(conn, args.query, args.provider, args.category, args.flag, args.limit, args.offset, args.like)
        elif args.command == "get":
            result = get(conn, args.identifier)
        else:
            result = stats(conn)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result is None: raise SystemExit(1)


if __name__ == "__main__":
    main()
