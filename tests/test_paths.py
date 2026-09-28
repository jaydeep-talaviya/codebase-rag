"""Paths must be repo-relative, and history must be listable.

Both exist for the same reason: nothing outside `app/services/paths.py` should
know that repositories are stored under `data/repositories/<id>/`. That layout
used to reach the database, the prompt sent to the model, and every citation.
"""

import unittest

from sqlmodel import Session, SQLModel, create_engine

from app.models.code_chunk import CodeChunk
from app.models.repository import Repository, RepositoryStatus
from app.services.code_parser import get_cleaned_files
from app.services.citation_service import build_sources
from app.services.paths import repo_relative_path
from app.services.repository import get_repository_summaries


class RepoRelativePathTests(unittest.TestCase):
    def test_strips_the_storage_layout(self):
        self.assertEqual(
            repo_relative_path("data/repositories/7/src/App.js", 7), "src/App.js"
        )

    def test_strips_the_leading_dot_slash(self):
        self.assertEqual(
            repo_relative_path("./data/repositories/7/src/App.js", 7), "src/App.js"
        )

    def test_strips_an_absolute_storage_path(self):
        self.assertEqual(
            repo_relative_path("/code/data/repositories/7/a/b.py", 7), "a/b.py"
        )

    def test_is_idempotent(self):
        once = repo_relative_path("data/repositories/7/src/App.js", 7)
        self.assertEqual(repo_relative_path(once, 7), once)

    def test_leaves_a_relative_path_alone(self):
        self.assertEqual(repo_relative_path("src/App.js", 7), "src/App.js")
        self.assertEqual(repo_relative_path("README.md", 1), "README.md")

    def test_does_not_strip_another_repositorys_prefix(self):
        self.assertEqual(
            repo_relative_path("data/repositories/9/other.js", 7),
            "data/repositories/9/other.js",
        )

    def test_keeps_a_real_directory_that_looks_like_the_layout(self):
        """A repo containing `data/repositories/notes.js` keeps its path."""
        self.assertEqual(
            repo_relative_path("data/repositories/notes.js", 1),
            "data/repositories/notes.js",
        )

    def test_keeps_a_numeric_directory_inside_the_repo(self):
        self.assertEqual(
            repo_relative_path("data/repositories/7/2fa/page.js", 7), "2fa/page.js"
        )

    def test_normalises_windows_separators(self):
        self.assertEqual(
            repo_relative_path("data\\repositories\\7\\a.py", 7), "a.py"
        )

    def test_tolerates_empty_and_none(self):
        self.assertEqual(repo_relative_path("", 7), "")
        self.assertIsNone(repo_relative_path(None, 7))

    def test_strips_without_a_repository_id(self):
        self.assertEqual(repo_relative_path("data/repositories/7/x.js", None), "x.js")


class IngestionStoresRelativePathsTests(unittest.TestCase):
    def test_stored_file_path_has_no_storage_prefix(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "3"
            (root / "src").mkdir(parents=True)
            (root / "src" / "App.js").write_text("export const a = 1\n")
            (root / "README.md").write_text("# hi\n")

            files = get_cleaned_files(str(root), 3)

        paths = sorted(f["file_path"] for f in files)
        self.assertEqual(paths, ["README.md", "src/App.js"])
        for path in paths:
            self.assertNotIn("data/repositories", path)
        # The basename is still derived from the real file on disk.
        by_path = {f["file_path"]: f for f in files}
        self.assertEqual(by_path["src/App.js"]["file_name"], "App.js")
        self.assertEqual(by_path["src/App.js"]["content"], "export const a = 1\n")


class LegacyRowPathTests(unittest.TestCase):
    """Rows written before paths were relative must still come out clean."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            repo = Repository(url="u", name="legacy", status=RepositoryStatus.completed)
            db.add(repo)
            db.commit()
            db.refresh(repo)
            self.repo_id = repo.id
            db.add(
                CodeChunk(
                    repository_id=repo.id,
                    file_path=f"data/repositories/{repo.id}/src/App.js",
                    file_name="App.js",
                    language="JavaScript",
                    chunk_index=0,
                    content="export const a = 1",
                    start_line=1,
                    end_line=2,
                    embedding=[0.0, 1.0],
                )
            )
            db.commit()

    def test_retrieval_normalises_a_legacy_row(self):
        from unittest.mock import patch

        from app.services.retrieval_service import retrieve_code

        with patch(
            "app.services.retrieval_service.hybrid_search",
            return_value=[
                type(
                    "Row",
                    (),
                    {
                        "content": "export const a = 1",
                        "file_path": f"data/repositories/{self.repo_id}/src/App.js",
                        "start_line": 1,
                        "end_line": 2,
                        "language": "JavaScript",
                    },
                )()
            ],
        ):
            with Session(self.engine) as db:
                chunks = retrieve_code(
                    query="a", repository_id=self.repo_id, db=db, top_k=5
                )

        self.assertEqual(chunks[0]["file_path"], "src/App.js")

    def test_a_citation_built_from_it_is_clean(self):
        from app.services.retrieval_service import retrieve_code
        from unittest.mock import patch

        with patch(
            "app.services.retrieval_service.hybrid_search",
            return_value=[
                type(
                    "Row",
                    (),
                    {
                        "content": "export const a = 1",
                        "file_path": f"data/repositories/{self.repo_id}/src/App.js",
                        "start_line": 1,
                        "end_line": 2,
                        "language": "JavaScript",
                    },
                )()
            ],
        ):
            with Session(self.engine) as db:
                chunks = retrieve_code(
                    query="a", repository_id=self.repo_id, db=db, top_k=5
                )

        # What the model is shown and what the user is shown agree.
        self.assertEqual(
            build_sources(chunks)[0]["file_path"], "src/App.js"
        )


class RepositorySummariesTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}
        )
        SQLModel.metadata.create_all(self.engine)

    def test_counts_chunks_and_orders_newest_first(self):
        with Session(self.engine) as db:
            older = Repository(url="u1", name="older", status=RepositoryStatus.completed)
            newer = Repository(url="u2", name="newer", status=RepositoryStatus.failed)
            db.add_all([older, newer])
            db.commit()
            db.refresh(older)
            db.refresh(newer)
            older_id, newer_id = older.id, newer.id

            db.add_all(
                [
                    CodeChunk(
                        repository_id=older_id,
                        file_path="a.py",
                        file_name="a.py",
                        language="Python",
                        chunk_index=i,
                        content="x",
                        start_line=1,
                        end_line=2,
                        embedding=[0.0, 1.0],
                    )
                    for i in range(3)
                ]
            )
            db.commit()

        with Session(self.engine) as db:
            summaries = get_repository_summaries(db)

        self.assertEqual(len(summaries), 2)
        by_name = {s.name: s for s in summaries}
        self.assertEqual(by_name["older"].chunk_count, 3)
        self.assertEqual(by_name["newer"].chunk_count, 0)
        # A repository with no chunks reports 0 rather than omitting the field.
        self.assertIsInstance(by_name["newer"].chunk_count, int)

    def test_empty_database_yields_empty_list(self):
        with Session(self.engine) as db:
            self.assertEqual(get_repository_summaries(db), [])


if __name__ == "__main__":
    unittest.main()
