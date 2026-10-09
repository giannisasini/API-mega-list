#!/usr/bin/env python3
"""Offline regression tests: parser edge cases, source coverage and safe search."""
import hashlib
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "netlogik"))
import build_catalog as build
import catalog


class ParserTests(unittest.TestCase):
    def test_link_balancing_and_escaped_pipe(self):
        line = r"| [Vendor [v2] \| Search](https://example.com/a_(b)?input=x&fpr=affiliate) | Useful \| pipe and (parenthesis). |"
        cells = build.split_table_row(line)
        self.assertEqual(len(cells), 2)
        name, url, end = build.markdown_link(cells[0])
        self.assertEqual(name, "Vendor [v2] | Search")
        self.assertEqual(url, "https://example.com/a_(b)?input=x&fpr=affiliate")
        self.assertEqual(end, len(cells[0]))

    def test_tracking_removal_preserves_functional_query_and_fragment(self):
        url = "https://EXAMPLE.com/a/?token=a%2Fb&fpr=partner&utm_source=news&ref=product&empty=#part"
        canonical, removed = build.canonicalize_url(url)
        self.assertEqual(canonical, "https://example.com/a/?token=a%2Fb&ref=product&empty=#part")
        self.assertEqual(removed, ["fpr=partner", "utm_source=news"])

    def test_table_rows_recovered_or_quarantined_without_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / "README.md"
            path.write_text("# AI\n| API Name | Description |\n|---|---|\n"
                            r"| [Good \| API](https://example.com/a_(b)) | Good \| description |" + "\n"
                            "| [Broken [label](https://example.com/b) | Fully recoverable. |\n"
                            "| [No target] | Preserve for review |\n", encoding="utf-8")
            rows, errors, candidates = build.parse_table_file(source, path, "core_category", "AI")
            self.assertEqual((candidates, len(rows), len(errors)), (3, 2, 1))
            self.assertEqual(rows[0]["description"], "Good | description")
            self.assertEqual(rows[1]["parse_warnings"], ["recovered_unbalanced_markdown_label"])
            self.assertIn("[No target]", errors[0]["raw"])

    def test_raw_multiline_internal_heading_does_not_change_category(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            path = source / "ACTORS.md"
            path.write_text("## AI\n- **[Same Name](https://apify.com/owner/first?fpr=x)** - Start.\n\n"
                            "## Features\n- Feature one\n- Feature two\n"
                            "- **[Same Name](https://apify.com/owner/second)** - Second actor.\n\n---\n"
                            "*Total: 2 Actors*\n*Last updated: yesterday*", encoding="utf-8")
            rows, errors, count = build.parse_raw_actors(source, path, {"ai"})
            self.assertEqual((len(rows), len(errors), count), (2, 0, 2))
            self.assertEqual(rows[0]["category"], "ai")
            self.assertIn("## Features - Feature one - Feature two", rows[0]["description"])
            self.assertEqual(rows[1]["description"], "Second actor.")

    def test_dedupe_exact_url_only_and_prefer_full_actor_description(self):
        rows = [build.make_occurrence("core.md", 1, "AI", "core_category", "Same Name", "https://apify.com/x/one?fpr=a", "Truncated..."),
                build.make_occurrence("raw.md", 2, "AI", "raw_actor", "Same Name", "https://apify.com/x/one?fpr=b", "Complete original description."),
                build.make_occurrence("raw.md", 3, "AI", "raw_actor", "Same Name", "https://apify.com/x/two", "Distinct actor."),
                build.make_occurrence("sponsored.md", 4, "AI", "sponsored", "Partner", "https://apyhub.com/utility/test", "Source cost is $1.")]
        entries = build.merge_occurrences(rows)
        self.assertEqual(len(entries), 3)
        first = next(e for e in entries if e["actor"] == {"owner": "x", "slug": "one"})
        self.assertEqual(first["description"], "Complete original description.")
        self.assertEqual(len(first["provenance"]), 2)
        self.assertIn("source_description_truncated", first["flags"])
        self.assertNotIn("description_truncated", first["flags"])
        self.assertIn("description_enriched", first["flags"])
        partner = next(e for e in entries if e["provider"] == "apyhub")
        self.assertIn("sponsored", partner["flags"])
        self.assertIn("unverified_pricing_claim", partner["flags"])
        self.assertEqual(partner["verification"]["pricing"], "unverified")


class BuiltCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dist = ROOT / "netlogik/dist"
        cls.data = json.loads(gzip.decompress((cls.dist / "catalog.json.gz").read_bytes()))
        cls.conn = catalog.connect(cls.dist / "catalog.sqlite")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_complete_coverage_and_measured_counts(self):
        stats = catalog.stats(self.conn)
        self.assertEqual(stats["entries"], 11981)
        self.assertEqual(stats["core_unique_entries"], 11660)
        self.assertEqual(stats["sponsored_unique_entries"], 318)
        self.assertEqual(stats["core_categories"], 23)
        self.assertEqual(stats["raw_only_entries"], 3)
        self.assertEqual(stats["quarantined_rows"], 0)
        self.assertEqual(stats["recovered_source_rows"], 9)
        self.assertEqual(sum(row["parsed_rows"] for row in stats["source_coverage"]), sum(len(e["provenance"]) for e in self.data["entries"]))
        for row in stats["source_coverage"]:
            self.assertEqual(row["candidate_rows"], row["parsed_rows"] + row["quarantined_rows"])
            source = ROOT / ("UPSTREAM_README.md" if row["path"] == "README.md" else row["path"])
            self.assertEqual(row["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(stats["root_only_entries"], 0)
        self.assertEqual(stats["root_missing_core_entries"], 0)

    def test_every_json_entry_roundtrips_through_sqlite(self):
        actual = {row[0]: json.loads(row[1]) for row in self.conn.execute("SELECT id,document FROM entries")}
        self.assertEqual(len(actual), len(self.data["entries"]))
        for entry in self.data["entries"]:
            self.assertEqual(actual[entry["id"]], entry)
            self.assertEqual(entry["id"], "api_" + hashlib.sha256(entry["canonical_url"].encode()).hexdigest()[:16])
            self.assertIn("unverified", entry["flags"])

    def test_search_filter_and_like_fallback(self):
        for force_like in (False, True):
            results = catalog.search(self.conn, "invoice", provider="apyhub", flag="sponsored", limit=4, force_like=force_like)
            self.assertGreater(results["total"], 0)
            self.assertLessEqual(len(results["entries"]), 4)
            self.assertTrue(all(e["provider"] == "apyhub" and "sponsored" in e["flags"] for e in results["entries"]))
        greek = catalog.search(self.conn, "ακίνητα", category="real-estate", limit=1)
        self.assertGreater(greek["total"], 0)
        self.assertIn("real-estate", greek["entries"][0]["categories"])
        greek_fallback = catalog.search(self.conn, "ακινητα", category="real-estate", limit=1, force_like=True)
        self.assertGreater(greek_fallback["total"], 0)

    def test_sql_and_fts_payloads_are_data(self):
        malicious = "' OR 1=1; DROP TABLE entries; --"
        self.assertIsNone(catalog.get(self.conn, malicious))
        for force_like in (False, True):
            result = catalog.search(self.conn, "invoice", provider=malicious, force_like=force_like)
            self.assertEqual(result["total"], 0)
            catalog.search(self.conn, malicious, force_like=force_like)
            self.assertEqual(catalog.search(self.conn, "!!!", force_like=force_like)["total"], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM entries").fetchone()[0], 11981)
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.execute("DELETE FROM entries")

    def test_raw_only_test_actors_retained_and_flagged(self):
        results = catalog.search(self.conn, flag="raw_only")
        self.assertEqual(results["total"], 3)
        self.assertEqual({e["actor"]["owner"] for e in results["entries"]}, {"fortuitous_pirate", "mitch320", "muhammetakkurtt"})


if __name__ == "__main__":
    unittest.main()
