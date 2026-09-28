"""Tests for idle repository expiry.

The failure modes that matter here are quiet ones: a sweeper that deletes a
repository someone is actively using, a sweeper that never fires because
something keeps refreshing the timestamp, and a partial delete that leaves
chunks nobody can reach.
"""

import shutil
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine

from app.models.code_chunk import CodeChunk
from app.models.repository import Repository, RepositoryStatus
from app.services.cleanup import (
    delete_repository,
    find_expired_repositories,
    sweep_once,
    touch_repositories,
)
from app.services.paths import REPOSITORY_STORAGE_ROOT

HOURS_AGO = timedelta(hours=1)


def make_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def make_repo(db, last_accessed: datetime, status=RepositoryStatus.completed):
    repo = Repository(
        url="https://github.com/acme/widget",
        name="widget",
        status=status,
        last_accessed_at=last_accessed,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def add_chunk(db, repository_id: int):
    chunk = CodeChunk(
        repository_id=repository_id,
        file_path="a.py",
        file_name="a.py",
        language="Python",
        chunk_index=0,
        content="print('hi')",
        start_line=1,
        end_line=1,
        embedding=[0.1, 0.2],
    )
    db.add(chunk)
    db.commit()
    return chunk


class StorageRootMixin:
    """Point storage at a temp directory so tests never touch the real clones."""

    def setUp(self):
        super().setUp()
        self._tmp = Path(__file__).parent / "_cleanup_tmp"
        if self._tmp.exists():
            shutil.rmtree(self._tmp)
        self._tmp.mkdir(parents=True)
        root = str(self._tmp / "repositories")
        self._patcher = patch(
            "app.services.cleanup.REPOSITORY_STORAGE_ROOT", root
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        self.addCleanup(self._cleanup_tmp)
        self._cleanup_tmp()

    def _cleanup_tmp(self):
        if self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)

    def make_clone(self, repository_id: int) -> Path:
        target = self._tmp / "repositories" / str(repository_id)
        (target / "src").mkdir(parents=True)
        (target / "src" / "a.py").write_text("print('hi')")
        return target


class ExpirySelectionTests(unittest.TestCase):
    """Which repositories qualify for deletion."""

    def setUp(self):
        self.engine = make_engine()

    def test_only_idle_repositories_expire(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            stale = make_repo(db, now - timedelta(hours=13))
            fresh = make_repo(db, now - timedelta(minutes=5))
            expired = find_expired_repositories(db, ttl_hours=12)

        self.assertIn(stale.id, expired)
        self.assertNotIn(fresh.id, expired)

    def test_repository_being_indexed_is_never_swept(self):
        """A live index has open handles into its own clone and rows.

        Deleting it leaves a half-written index and a `processing` status that
        nobody can finish.
        """
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            busy = make_repo(
                db, now - timedelta(hours=99), status=RepositoryStatus.processing
            )
            self.assertNotIn(busy.id, find_expired_repositories(db, ttl_hours=12))

    def test_boundary_is_inclusive_of_older_than_ttl(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            just_inside = make_repo(db, now - timedelta(hours=11, minutes=59))
            just_outside = make_repo(db, now - timedelta(hours=12, minutes=1))
            inside_id, outside_id = just_inside.id, just_outside.id
            expired = find_expired_repositories(db, ttl_hours=12)

        self.assertNotIn(inside_id, expired)
        self.assertIn(outside_id, expired)


class TouchTests(unittest.TestCase):
    def setUp(self):
        self.engine = make_engine()

    def test_touch_pushes_expiry_out(self):
        stale = datetime.now(timezone.utc) - timedelta(hours=20)
        with Session(self.engine) as db:
            repo = make_repo(db, stale)
            self.assertIn(repo.id, find_expired_repositories(db, ttl_hours=12))

            self.assertEqual(touch_repositories(db, [repo.id]), 1)
            self.assertNotIn(repo.id, find_expired_repositories(db, ttl_hours=12))

    def test_touch_handles_empty_and_none(self):
        with Session(self.engine) as db:
            self.assertEqual(touch_repositories(db, []), 0)
            self.assertEqual(touch_repositories(db, [None]), 0)

    def test_touch_updates_many_in_one_pass(self):
        with Session(self.engine) as db:
            repos = [
                make_repo(db, datetime.now(timezone.utc) - timedelta(hours=20))
                for _ in range(3)
            ]
            ids = [r.id for r in repos]
            self.assertEqual(touch_repositories(db, ids), 3)
            self.assertEqual(find_expired_repositories(db, ttl_hours=12), [])


class DeletionTests(StorageRootMixin, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.engine = make_engine()

    def test_removes_clone_chunks_and_row(self):
        with Session(self.engine) as db:
            repo = make_repo(db, datetime.now(timezone.utc) - timedelta(hours=20))
            add_chunk(db, repo.id)
            clone = self.make_clone(repo.id)
            self.assertTrue(clone.is_dir())

            self.assertTrue(delete_repository(repo.id, db))

            self.assertFalse(clone.exists(), "clone directory should be gone")
            self.assertEqual(
                db.query(CodeChunk).filter(CodeChunk.repository_id == repo.id).count(),
                0,
                "chunks should be gone",
            )
            self.assertIsNone(db.get(Repository, repo.id), "row should be gone")

    def test_second_pass_is_a_no_op(self):
        with Session(self.engine) as db:
            repo = make_repo(db, datetime.now(timezone.utc) - timedelta(hours=20))
            add_chunk(db, repo.id)
            self.make_clone(repo.id)

            self.assertTrue(delete_repository(repo.id, db))
            # A retry after a partial failure, or a second sweeper, must not
            # raise just because there is nothing left to delete.
            self.assertTrue(delete_repository(repo.id, db))

    def test_failed_directory_removal_keeps_rows_for_retry(self):
        """The clone goes first, so a failure there must not lose the pointer.

        Dropping the rows anyway would strand chunks and a directory that
        nothing references, with no way to find them again.
        """
        with Session(self.engine) as db:
            repo = make_repo(db, datetime.now(timezone.utc) - timedelta(hours=20))
            add_chunk(db, repo.id)
            self.make_clone(repo.id)

            with patch(
                "app.services.cleanup.shutil.rmtree",
                side_effect=OSError("permission denied"),
            ):
                self.assertFalse(delete_repository(repo.id, db))

            self.assertIsNotNone(db.get(Repository, repo.id), "row must survive")
            self.assertEqual(
                db.query(CodeChunk).filter(CodeChunk.repository_id == repo.id).count(),
                1,
                "chunks must survive",
            )

    def test_sweep_clears_idle_and_keeps_active(self):
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            stale = make_repo(db, now - timedelta(hours=20))
            fresh = make_repo(db, now - timedelta(minutes=1))
            add_chunk(db, stale.id)
            self.make_clone(stale.id)

            removed = sweep_once(db, ttl_hours=12)

            self.assertEqual(removed, [stale.id])
            self.assertIsNone(db.get(Repository, stale.id))
            self.assertIsNotNone(db.get(Repository, fresh.id))
            self.assertTrue((self._tmp / "repositories" / str(stale.id)).exists() is False)

    def test_clone_path_cannot_escape_the_storage_root(self):
        """The id is coerced to int, so no caller-supplied path can reach rmtree."""
        from app.services.cleanup import _clone_path

        with self.assertRaises(ValueError):
            _clone_path("../../etc")


class HistoryListDoesNotKeepReposAliveTests(unittest.TestCase):
    """The frontend loads the history list on every page render.

    If that counted as "use", every stored repository would be refreshed forever
    and the sweeper would never remove anything.
    """

    def setUp(self):
        self.engine = make_engine()

    def test_listing_history_leaves_timestamp_untouched(self):
        from app.services.repository import get_repository_summaries

        with Session(self.engine) as db:
            repo = make_repo(db, datetime.now(timezone.utc) - timedelta(hours=20))
            add_chunk(db, repo.id)
            before = db.get(Repository, repo.id).last_accessed_at

            get_repository_summaries(db)

            after = db.get(Repository, repo.id).last_accessed_at
            self.assertEqual(before, after)
            # And it is still eligible, which is the behaviour that matters.
            self.assertIn(repo.id, find_expired_repositories(db, ttl_hours=12))


if __name__ == "__main__":
    unittest.main()
