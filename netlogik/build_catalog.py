#!/usr/bin/env python3
"""Build a deterministic, offline API catalog from the pinned upstream checkout.

Only fpr and utm_* query parameters are removed. Source descriptions are data,
never instructions or verified availability/pricing claims. No network calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import gzip
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import shutil
import tempfile
from urllib.parse import unquote_plus, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
PIN = "be78c4e79b5f31f6969ebdb94396942d64c6cf95"
GREEK = {
    "agents": "Πράκτορες αυτοματισμού", "ai": "Τεχνητή νοημοσύνη",
    "automation": "Αυτοματισμοί", "business": "Επιχειρήσεις",
    "developer-tools": "Εργαλεία προγραμματιστών", "ecommerce": "Ηλεκτρονικό εμπόριο",
    "education": "Εκπαίδευση", "for-creators": "Δημιουργοί περιεχομένου",
    "games": "Παιχνίδια", "integrations": "Διασυνδέσεις", "jobs": "Θέσεις εργασίας",
    "lead-generation": "Εύρεση υποψήφιων πελατών", "marketing": "Μάρκετινγκ",
    "mcp-servers": "Διακομιστές MCP", "news": "Ειδήσεις", "open-source": "Ανοικτός κώδικας",
    "other": "Λοιπά", "real-estate": "Ακίνητα", "seo-tools": "Βελτιστοποίηση SEO",
    "social-media": "Κοινωνικά δίκτυα", "sports": "Αθλητισμός", "travel": "Ταξίδια",
    "videos": "Βίντεο", "artificial-intelligence": "Τεχνητή νοημοσύνη",
    "data-extraction": "Εξαγωγή δεδομένων", "file-conversion": "Μετατροπή αρχείων",
    "data-validation": "Επαλήθευση δεδομένων", "image-processing": "Επεξεργασία εικόνας",
}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def clean_text(value):
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = html.unescape(value).replace(r"\|", "|").replace(r"\]", "]").replace(r"\[", "[")
    return " ".join(value.split())


def slug(value):
    return re.sub(r"[^\w]+", "-", value.replace("_", "-").casefold()).strip("-")


def canonicalize_url(url):
    """Retain functional query bytes/order, fragments, paths and unknown ref values."""
    url = html.unescape(url.strip().strip("<>"))
    parsed = urlsplit(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username:
        raise ValueError("Listing URL must be an absolute HTTP(S) URL without userinfo")
    kept, removed = [], []
    for part in parsed.query.split("&") if parsed.query else []:
        key = unquote_plus(part.split("=", 1)[0]).casefold()
        if key == "fpr" or key.startswith("utm_"):
            removed.append(part)
        else:
            kept.append(part)
    canonical = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "&".join(kept), parsed.fragment))
    return canonical, removed


def markdown_link(text, start=0):
    """Parse a link with escaped brackets and balanced URL parentheses."""
    pos = text.find("[", start)
    if pos < 0:
        raise ValueError("Missing Markdown link")
    title_start, depth, i = pos + 1, 1, pos + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if not depth:
                break
        i += 1
    if i + 1 >= len(text) or text[i + 1] != "(":
        raise ValueError("Incomplete Markdown link label")
    title, url_start, depth, j = text[title_start:i], i + 2, 1, i + 2
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if not depth:
                break
        j += 1
    if depth:
        raise ValueError("Unclosed Markdown URL")
    url = text[url_start:j].strip()
    if url.startswith("<") and ">" in url:
        url = url[1:url.index(">")]
    # A Markdown optional title is not part of the URL.
    url = re.split(r'\s+[\"\']', url, maxsplit=1)[0]
    return clean_text(title), url, j + 1


def listing_link(text):
    """Recover one known source defect: an unmatched '[' inside a link label.

    Require an unambiguous HTTP(S) target; preserve the complete defective line
    in provenance so this recovery is reviewable, never a silent repair.
    """
    try:
        return (*markdown_link(text), [])
    except ValueError:
        start = text.find("[")
        target = re.search(r"\]\((https?://[^\s]+)\)", text)
        if start < 0 or not target or target.start() <= start:
            raise
        name = clean_text(text[start + 1:target.start()])
        url = target[1]
        canonicalize_url(url)
        return name, url, target.end(), ["recovered_unbalanced_markdown_label"]


def split_table_row(line):
    """Split two-column Markdown safely around escaped pipes and link labels."""
    cells, buffer = [], []
    brackets = parentheses = 0
    code = False
    i = 0
    for_start = line.strip()
    while i < len(for_start):
        char = for_start[i]
        if char == "\\" and i + 1 < len(for_start):
            buffer.extend(for_start[i:i + 2]); i += 2; continue
        if char == "`":
            code = not code
        elif not code:
            if char == "[": brackets += 1
            elif char == "]": brackets = max(0, brackets - 1)
            elif char == "(": parentheses += 1
            elif char == ")": parentheses = max(0, parentheses - 1)
            elif char == "|" and not brackets and not parentheses:
                cells.append("".join(buffer).strip()); buffer = []; i += 1; continue
        buffer.append(char); i += 1
    cells.append("".join(buffer).strip())
    if cells and not cells[0]: cells.pop(0)
    if cells and not cells[-1]: cells.pop()
    return cells


def truncated(description):
    return bool(re.search(r"(?:\.{3}|…)[\s*_]*$", description))


def make_occurrence(path, line, category, source_kind, name, url, description):
    canonical, removed = canonicalize_url(url)
    host = urlsplit(canonical).hostname
    provider = {"apify.com": "apify", "apyhub.com": "apyhub", "www.coreclaw.com": "coreclaw", "coreclaw.com": "coreclaw"}.get(host, host)
    parts = urlsplit(canonical).path.strip("/").split("/")
    actor = {"owner": parts[0], "slug": parts[1]} if provider == "apify" and len(parts) == 2 else None
    return {"canonical_url": canonical, "provider": provider, "actor": actor,
            "name": name, "description": clean_text(description), "category": slug(category),
            "source_category": category, "path": path, "line": line, "source_kind": source_kind,
            "original_url": url, "removed_tracking_parameters": removed,
            "description_truncated": truncated(description)}


def parse_table_file(source, path, source_kind, category=None):
    rows, quarantine, candidates = [], [], 0
    current = category
    active = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("#"):
            active = False
            if category is None:
                current = re.sub(r"^#+\s*", "", line).strip()
        if re.match(r"^\|\s*API Name\s*\|\s*Description", line, re.I):
            active = True
            continue
        if not active or not line.lstrip().startswith("|"):
            continue
        if re.fullmatch(r"[|\s:\-]+", line):
            continue
        candidates += 1
        try:
            name, url, end, warnings = listing_link(line)
            remainder = line[end:].strip()
            if not remainder.startswith("|"):
                raise ValueError("Expected description cell after listing link")
            description = remainder[1:].strip()
            if description.endswith("|"): description = description[:-1].rstrip()
            row = make_occurrence(str(path.relative_to(source)), number, current or "Uncategorized", source_kind, name, url, description)
            if warnings:
                row.update(parse_warnings=warnings, raw_source_line=line)
            rows.append(row)
        except ValueError as exc:
            quarantine.append({"path": str(path.relative_to(source)), "line": number, "raw": line, "error": str(exc)})
    return rows, quarantine, candidates


def parse_raw_actors(source, path, core_categories):
    rows, quarantine, candidates = [], [], 0
    category = "Uncategorized"
    pending = None
    lines = path.read_text(encoding="utf-8").splitlines()

    def finish():
        nonlocal pending
        if pending:
            number, name, url, pieces, warnings, raw_line = pending
            try:
                row = make_occurrence(str(path.relative_to(source)), number, category, "raw_actor", name, url, "\n".join(pieces).strip())
                if warnings: row.update(parse_warnings=warnings, raw_source_line=raw_line)
                rows.append(row)
            except ValueError as exc:
                quarantine.append({"path": str(path.relative_to(source)), "line": number, "raw": "\n".join(lines[number - 1:number] + pieces[1:]), "error": str(exc)})
            pending = None

    for number, line in enumerate(lines, 1):
        heading = re.match(r"^##\s+(.+)$", line)
        if heading and slug(heading[1]) in core_categories:
            finish(); category = heading[1]; continue
        if line.startswith("*Total:"):
            finish(); break
        if line.startswith("- **["):
            candidates += 1
            finish()
            try:
                name, url, end, warnings = listing_link(line)
                remainder = re.sub(r"^\*\*\s*[-—]\s*", "", line[end:])
                pending = (number, name, url, [remainder], warnings, line)
            except ValueError as exc:
                quarantine.append({"path": str(path.relative_to(source)), "line": number, "raw": line, "error": str(exc)})
        elif pending:
            if line == "---" and all(not item.strip() or item.startswith(("*Total:", "*Last updated:")) for item in lines[number:]):
                finish(); break
            pending[3].append(line)
    finish()
    return rows, quarantine, candidates


def parse_coreclaw(source, path):
    rows, quarantine, candidates = [], [], 0
    category = "CoreClaw"
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("### "):
            category = re.sub(r"\s+\(\d+\)$", "", line[4:])
        if not line.startswith("- ["):
            continue
        candidates += 1
        try:
            name, url, end = markdown_link(line)
            description = re.sub(r"^\s*—\s*`[^`]+`\s*—\s*", "", line[end:])
            rows.append(make_occurrence(str(path.relative_to(source)), number, category, "sponsored", name, url, description))
        except ValueError as exc:
            quarantine.append({"path": str(path.relative_to(source)), "line": number, "raw": line, "error": str(exc)})
    return rows, quarantine, candidates


def merge_occurrences(occurrences):
    grouped = {}
    for row in occurrences:
        grouped.setdefault(row["canonical_url"], []).append(row)
    entries = []
    for canonical, rows in sorted(grouped.items()):
        # An exact canonical actor ID is required for raw-description enrichment.
        best = max(rows, key=lambda r: (not r["description_truncated"], r["source_kind"] == "raw_actor", len(r["description"])))
        categories = sorted({r["category"] for r in rows})
        flags = {"unverified"}
        if all(r["source_kind"] == "raw_actor" for r in rows): flags.add("raw_only")
        if any(r.get("parse_warnings") for r in rows): flags.add("recovered_source_markup")
        if any(r["source_kind"] == "sponsored" for r in rows): flags.add("sponsored")
        if best["description_truncated"]: flags.add("description_truncated")
        if any(r["description_truncated"] for r in rows): flags.add("source_description_truncated")
        if any(r["removed_tracking_parameters"] for r in rows): flags.add("tracking_removed")
        if best["source_kind"] == "raw_actor" and any(r["description"] != best["description"] for r in rows): flags.add("description_enriched")
        claims = []
        if re.search(r"\b(?:free|pricing|price|cost|credits|per[- ](?:result|request)|pay[- ]per)\b|[$€£]\s*\d", best["name"] + " " + best["description"], re.I):
            claims.append("pricing_or_cost")
            flags.add("unverified_pricing_claim")
        entry = {"id": "api_" + hashlib.sha256(canonical.encode()).hexdigest()[:16],
                 "name": best["name"], "description": best["description"], "canonical_url": canonical,
                 "provider": best["provider"], "actor": best["actor"], "categories": categories,
                 "category_labels_el": sorted({GREEK[c] for c in categories if c in GREEK}),
                 "flags": sorted(flags), "verification": {"availability": "unverified", "pricing": "unverified", "authentication": "unverified", "input_schema": "unverified"},
                 "unverified_claim_types": claims,
                 "description_source": {"path": best["path"], "line": best["line"], "source_kind": best["source_kind"]},
                 "provenance": [{k: v for k, v in row.items() if k not in ("canonical_url", "provider", "actor")}
                                for row in sorted(rows, key=lambda r: (r["path"], r["line"]))]}
        entries.append(entry)
    if len({e["id"] for e in entries}) != len(entries):
        raise ValueError("Stable ID hash collision")
    return entries


def build_sqlite(path, catalog, stats):
    temporary = path.with_suffix(".sqlite.tmp")
    if temporary.exists(): temporary.unlink()
    conn = sqlite3.connect(temporary)
    conn.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE entries (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
          canonical_url TEXT NOT NULL UNIQUE, provider TEXT NOT NULL, search_text TEXT NOT NULL, document TEXT NOT NULL);
        CREATE TABLE category_memberships (entry_id TEXT NOT NULL REFERENCES entries(id), category TEXT NOT NULL,
          PRIMARY KEY(entry_id, category));
        CREATE TABLE entry_flags (entry_id TEXT NOT NULL REFERENCES entries(id), flag TEXT NOT NULL,
          PRIMARY KEY(entry_id, flag));
        CREATE TABLE provenance (entry_id TEXT NOT NULL REFERENCES entries(id), path TEXT NOT NULL, line INTEGER NOT NULL,
          original_url TEXT NOT NULL, source_kind TEXT NOT NULL, document TEXT NOT NULL,
          PRIMARY KEY(entry_id,path,line));
        CREATE INDEX entry_provider ON entries(provider);
        CREATE INDEX category_lookup ON category_memberships(category,entry_id);
        CREATE INDEX flag_lookup ON entry_flags(flag,entry_id);
    """)
    fts = True
    try:
        conn.execute("CREATE VIRTUAL TABLE entries_fts USING fts5(id UNINDEXED,name,description,search_text,tokenize='unicode61 remove_diacritics 2')")
    except sqlite3.OperationalError:
        fts = False
    for entry in catalog["entries"]:
        search_text = " ".join([entry["canonical_url"], entry["provider"], *entry["categories"], *entry["category_labels_el"]])
        conn.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?)", (entry["id"], entry["name"], entry["description"], entry["canonical_url"], entry["provider"], search_text, dumps(entry)))
        conn.executemany("INSERT INTO category_memberships VALUES (?,?)", [(entry["id"], category) for category in entry["categories"]])
        conn.executemany("INSERT INTO entry_flags VALUES (?,?)", [(entry["id"], flag) for flag in entry["flags"]])
        conn.executemany("INSERT INTO provenance VALUES (?,?,?,?,?,?)", [(entry["id"], p["path"], p["line"], p["original_url"], p["source_kind"], dumps(p)) for p in entry["provenance"]])
        if fts:
            conn.execute("INSERT INTO entries_fts VALUES (?,?,?,?)", (entry["id"], entry["name"], entry["description"], search_text))
    conn.executemany("INSERT INTO metadata VALUES (?,?)", [("schema_version", dumps(catalog["schema_version"])), ("source", dumps(catalog["source"])), ("stats", dumps(stats)), ("fts5", dumps(fts))])
    conn.commit()
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok": raise RuntimeError(integrity)
    conn.close()
    temporary.replace(path)
    return fts


def build(source, output, expected_commit=PIN, verified_snapshot=None):
    if verified_snapshot is None:
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
            raise ValueError("Pinned source has tracked modifications; use a clean checkout")
        source_date = subprocess.check_output(["git", "-C", str(source), "show", "-s", "--format=%cI", "HEAD"], text=True).strip()
    else:
        commit = verified_snapshot["source"]["commit"]
        source_date = verified_snapshot["source"]["commit_date"]
        for expected in verified_snapshot["files"]:
            relative = Path(expected["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid snapshot path")
            if hashlib.sha256((source / relative).read_bytes()).hexdigest() != expected["sha256"]:
                raise ValueError(f"Snapshot hash mismatch: {relative}")
    if expected_commit and commit != expected_commit:
        raise ValueError(f"Expected source commit {expected_commit}, found {commit}")
    categories = []
    for path in sorted(source.glob("*-apis-*/README.md")):
        heading = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
        categories.append((path, heading))
    occurrences, quarantine, coverage = [], [], []

    def collect(path, kind, result):
        rows, errors, candidates = result
        occurrences.extend(rows); quarantine.extend(errors)
        coverage.append({"path": str(path.relative_to(source)), "source_kind": kind,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "candidate_rows": candidates,
                         "parsed_rows": len(rows), "quarantined_rows": len(errors)})
        if candidates != len(rows) + len(errors): raise AssertionError("Unaccounted source rows")

    for path, heading in categories:
        collect(path, "core_category", parse_table_file(source, path, "core_category", heading))
    path = source / "README.md"
    collect(path, "root_duplicate", parse_table_file(source, path, "root_duplicate"))
    path = source / "settings/APIFY_ACTORS.md"
    collect(path, "raw_actor", parse_raw_actors(source, path, {slug(c) for _, c in categories}))
    path = source / "00-featured-apis/apyhub-utility-apis/README.md"
    collect(path, "sponsored", parse_table_file(source, path, "sponsored"))
    path = source / "00-featured-apis/coreclaw-scraper-apis/README.md"
    collect(path, "sponsored", parse_coreclaw(source, path))
    entries = merge_occurrences(occurrences)
    core_urls = {r["canonical_url"] for r in occurrences if r["source_kind"] == "core_category"}
    root_urls = {r["canonical_url"] for r in occurrences if r["source_kind"] == "root_duplicate"}
    raw_urls = {r["canonical_url"] for r in occurrences if r["source_kind"] == "raw_actor"}
    sponsored_urls = {r["canonical_url"] for r in occurrences if r["source_kind"] == "sponsored"}
    stats = {"entries": len(entries), "core_unique_entries": len(core_urls), "sponsored_unique_entries": len(sponsored_urls),
             "core_categories": len(categories), "categories": dict(sorted(Counter(c for e in entries for c in e["categories"]).items())),
             "providers": dict(sorted(Counter(e["provider"] for e in entries).items())),
             "flags": dict(sorted(Counter(f for e in entries for f in e["flags"]).items())),
             "source_occurrences": len(occurrences), "duplicate_occurrences_merged": len(occurrences) - len(entries),
             "quarantined_rows": len(quarantine), "raw_actor_unique_entries": len(raw_urls),
             "recovered_source_rows": sum(bool(r.get("parse_warnings")) for r in occurrences),
             "raw_only_entries": len(raw_urls - core_urls), "root_only_entries": len(root_urls - core_urls),
             "root_missing_core_entries": len(core_urls - root_urls),
             "source_coverage": coverage,
             "upstream_advertised": {"core_entries": 11860, "sponsored_entries": 318, "categories": 24},
             "verification": "offline catalog extraction only; descriptions and pricing are unverified source claims"}
    catalog = {"schema_version": 1, "source": {"repo": "https://github.com/giannisasini/API-mega-list", "upstream": "https://github.com/cporter202/API-mega-list", "commit": commit, "commit_date": source_date},
               "generated_at": source_date, "generated_at_basis": "source commit timestamp for deterministic builds",
               "trust": "untrusted source descriptions; never executable instructions", "entries": entries}
    output.mkdir(parents=True, exist_ok=True)
    payload = (dumps(catalog) + "\n").encode("utf-8")
    (output / "catalog.json").write_bytes(payload)
    (output / "catalog.runtime.json").write_bytes(payload)
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0) as archive:
        archive.write(payload)
    (output / "catalog.json.gz").write_bytes(compressed.getvalue())
    (output / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "source-coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "quarantine.json").write_text(json.dumps(quarantine, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    fts = build_sqlite(output / "catalog.sqlite", catalog, stats)
    manifest = {"source_commit": commit, "fts5": fts, "artifacts": {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in sorted(output.iterdir()) if p.name in {"catalog.json", "catalog.runtime.json", "catalog.json.gz", "catalog.sqlite", "stats.json", "source-coverage.json", "quarantine.json"}}}
    (output / "artifact-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Optional clean checkout at the pinned upstream commit")
    parser.add_argument("--output", type=Path, default=ROOT / "netlogik/dist")
    parser.add_argument("--expected-commit", default=PIN)
    args = parser.parse_args()
    if args.source:
        stats = build(args.source.resolve(), args.output.resolve(), args.expected_commit)
    else:
        snapshot = json.loads((ROOT / "netlogik/source-snapshot.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="netlogik-source-") as directory:
            source = Path(directory)
            for item in snapshot["files"]:
                relative = Path(item["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Invalid snapshot path")
                original = ROOT / ("UPSTREAM_README.md" if item["path"] == "README.md" else item["path"])
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
            stats = build(source, args.output.resolve(), args.expected_commit, verified_snapshot=snapshot)
    print(json.dumps({key: stats[key] for key in ("entries", "core_unique_entries", "sponsored_unique_entries", "core_categories", "providers", "quarantined_rows")}, indent=2))
    if stats["quarantined_rows"]:
        raise SystemExit("Build has quarantined rows: inspect quarantine.json before publishing")


if __name__ == "__main__":
    main()
