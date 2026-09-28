"""Tests for the retrieval-quality changes: noise exclusion, symbol extraction,
path-aware embedding text, and genuinely hybrid fusion."""
import unittest
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine

from app.models.code_chunk import CodeChunk
from app.models.repository import Repository
from app.services.code_parser import is_ignored
from app.services.embedding_service import embeddable_text
from app.services.symbols import extract_symbols
from app.services.vector_search import _fuse, escape_like


class NoiseExclusionTests(unittest.TestCase):
    """Lockfiles drown out real code if they are indexed at all."""

    def test_dependency_manifests_are_excluded(self):
        for name in (
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "poetry.lock",
            "Cargo.lock",
            "Gemfile.lock",
            "go.sum",
            "npm-shrinkwrap.json",
        ):
            with self.subTest(name=name):
                self.assertTrue(is_ignored(name), f"{name} should be excluded")

    def test_build_output_is_excluded(self):
        for name in ("bundle.min.js", "app.min.css", "vendor.bundle.js", "app.js.map"):
            with self.subTest(name=name):
                self.assertTrue(is_ignored(name))

    def test_real_source_is_still_indexed(self):
        """The exclusions must not be so broad that they eat real code."""
        for name in (
            "package.json",          # not a lockfile despite the prefix
            "composer.json",
            "config.py",
            "app.jsx",
            "index.ts",
            "Lockfile",              # no extension
            "lockfile.rs",
            "makefile",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_ignored(name), f"{name} should still be indexed")


class SymbolExtractionTests(unittest.TestCase):
    def test_python_definitions(self):
        src = "import os\n\nclass Store:\n    pass\n\ndef load(path):\n    return path\n\nasync def fetch():\n    pass\n"
        self.assertEqual(extract_symbols(src), ["Store", "load", "fetch"])

    def test_javascript_definitions(self):
        src = "export function go() {}\nconst x = (a) => a\nexport class Widget {}\nconst y = async () => 1\n"
        # Source order is preserved, so `x` precedes `Widget`.
        self.assertEqual(extract_symbols(src), ["go", "x", "Widget", "y"])

    def test_other_languages(self):
        self.assertEqual(extract_symbols("func Handle(w http.ResponseWriter) {}\n"), ["Handle"])
        self.assertEqual(extract_symbols("fn main() {}\nstruct Point { x: i32 }\n"), ["main", "Point"])
        self.assertEqual(extract_symbols("module vpc {\n}\n"), ["vpc"])

    def test_keywords_are_not_symbols(self):
        self.assertEqual(extract_symbols("if (x) {\n  return 1;\n}\n"), [])

    def test_duplicates_collapse_and_order_is_preserved(self):
        self.assertEqual(extract_symbols("def a():\n    pass\ndef b():\n    pass\ndef a():\n    pass\n"), ["a", "b"])

    def test_never_raises_on_junk(self):
        """A regex table is a hint; it must not be able to fail an index run."""
        for junk in ("", "\x00\x01", "{" * 5000, "def ", "class 1", "日本語 def 関数():"):
            with self.subTest(junk=junk[:20]):
                self.assertIsInstance(extract_symbols(junk), list)

    def test_symbol_list_is_capped(self):
        src = "".join(f"def fn_{i}():\n    pass\n" for i in range(200))
        self.assertLessEqual(len(extract_symbols(src)), 40)


class EmbeddableTextTests(unittest.TestCase):
    def test_path_is_included(self):
        text = embeddable_text("app/config.py", "DEBUG = False")
        self.assertIn("app/config.py", text)
        self.assertIn("DEBUG = False", text)

    def test_symbols_are_included(self):
        text = embeddable_text("a.py", "body", ["load", "save"])
        self.assertIn("load, save", text)

    def test_content_is_preserved_verbatim(self):
        """The stored content must stay clean even though the embedded text is decorated."""
        body = "def load():\n    return 1\n"
        self.assertTrue(embeddable_text("a.py", body, ["load"]).endswith(body))


class LikeEscapingTests(unittest.TestCase):
    def test_wildcards_are_escaped(self):
        self.assertEqual(escape_like("50%"), "50\\%")
        self.assertEqual(escape_like("a_b"), "a\\_b")

    def test_backslash_is_escaped_first(self):
        """Order matters, or the escapes of % and _ would be re-escaped."""
        self.assertEqual(escape_like("a\\%"), "a\\\\\\%")


class _Chunk:
    def __init__(self, cid):
        self.id = cid


class FusionTests(unittest.TestCase):
    """The regression that motivated fusion: keyword hits must survive."""

    def test_keyword_results_are_not_discarded(self):
        vector = [_Chunk(1), _Chunk(2), _Chunk(3), _Chunk(4), _Chunk(5)]
        keyword = [_Chunk(90), _Chunk(2)]
        fused = _fuse([vector, keyword])
        self.assertIn(90, [c.id for c in fused], "keyword-only chunk was dropped")

    def test_agreement_is_promoted(self):
        vector = [_Chunk(1), _Chunk(2), _Chunk(3)]
        keyword = [_Chunk(2), _Chunk(4)]
        fused = [c.id for c in _fuse([vector, keyword])]
        self.assertEqual(fused[0], 2, "a chunk found by both should rank first")

    def test_ordering_is_deterministic(self):
        a = [_Chunk(1), _Chunk(2)]
        b = [_Chunk(3), _Chunk(4)]
        self.assertEqual([c.id for c in _fuse([a, b])], [c.id for c in _fuse([a, b])])

    def test_empty_input(self):
        self.assertEqual(_fuse([[], []]), [])


class KeywordSearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            repo = Repository(url="u", name="r")
            db.add(repo)
            db.commit()
            db.refresh(repo)
            self.repo_id = repo.id
            db.add(CodeChunk(repository_id=repo.id, file_path="a.py", file_name="a.py",
                             language="Python", chunk_index=0, content="alpha keyword here",
                             start_line=1, end_line=1, embedding=[0.0, 1.0]))
            db.commit()

    def test_literal_percent_matches_literally(self):
        from app.services.vector_search import keyword_search

        with Session(self.engine) as db:
            db.add(CodeChunk(repository_id=self.repo_id, file_path="b.py", file_name="b.py",
                             language="Python", chunk_index=1, content="takes 50% off today",
                             start_line=1, end_line=1, embedding=[0.0, 1.0]))
            db.commit()
            # Unescaped, "%" is a wildcard and would match every row in the table.
            hits = keyword_search("50%", self.repo_id, db, top_k=10)
            self.assertEqual([h.content for h in hits], ["takes 50% off today"])

    def test_unfiltered_search_does_not_match_nothing(self):
        """repository_id=None previously compiled to `IS NULL` and returned zero rows."""
        from app.services.vector_search import keyword_search

        with Session(self.engine) as db:
            hits = keyword_search("alpha", None, db, top_k=10)
            self.assertEqual(len(hits), 1)


class RerankingHonestyTests(unittest.TestCase):
    def test_hybrid_returns_both_sides(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(engine)
        with Session(engine) as db:
            repo = Repository(url="u", name="r")
            db.add(repo)
            db.commit()
            db.refresh(repo)
            for i in range(3):
                db.add(CodeChunk(repository_id=repo.id, file_path=f"f{i}.py", file_name=f"f{i}.py",
                                 language="Python", chunk_index=i, content=f"chunk {i}",
                                 start_line=1, end_line=1, embedding=[0.0, 1.0]))
            db.commit()

        from app.services.vector_search import hybrid_search

        # Vector search returns everything, so a keyword-only row must still make
        # it into the fused output when one exists.
        with patch("app.services.vector_search.search_code", return_value=[]), \
             patch("app.services.vector_search.keyword_search", return_value=[_Chunk(7)]):
            with Session(engine) as db:
                self.assertEqual([c.id for c in hybrid_search("q", None, db, top_k=5)], [7])


if __name__ == "__main__":
    unittest.main()
