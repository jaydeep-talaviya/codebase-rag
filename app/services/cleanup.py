"""Idle expiry for stored repositories.

A repository occupies real space in two places: a git clone under
`data/repositories/{id}/`, and one `code_chunks` row per chunk, of which the
embedding is the largest part. Both are reclaimed here.

Expiry is keyed on `last_accessed_at` rather than `created_at`, so a repository
that is in active use is never deleted out from under the user.
"""

import logging
import shutil
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.code_chunk import CodeChunk
from app.models.repository import Repository, RepositoryStatus
from app.services.paths import REPOSITORY_STORAGE_ROOT

logger = logging.getLogger(__name__)

# Arbitrary but fixed: lets several uvicorn workers sweep without racing over
# the same rows. A constant rather than anything derived at runtime, because
# every process has to agree on the value.
_CLEANUP_LOCK_ID = 918_273_645


@contextmanager
def cleanup_lock(db: Session):
    """Serialize sweeps across processes.

    Without this, every uvicorn worker runs its own background task and they
    race: one deletes the rows while another is midway through deleting the same
    rows. Postgres advisory locks are session-scoped, so the unlock has to go
    through the same connection the lock was taken on.

    Non-Postgres backends (the SQLite engine used by tests) are single-process
    by construction, so there is nothing to serialize and the lock is skipped.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        yield True
        return

    acquired = db.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": _CLEANUP_LOCK_ID}
    ).scalar()
    try:
        yield bool(acquired)
    finally:
        if acquired:
            db.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": _CLEANUP_LOCK_ID}
            )


def touch_repositories(db: Session, repository_ids) -> int:
    """Mark repositories as used so the sweeper leaves them alone.

    One transaction regardless of how many ids there are, rather than a write
    per repository on every search.
    """
    ids = {int(i) for i in repository_ids if i is not None}
    if not ids:
        return 0

    now = datetime.now(timezone.utc)
    repositories = db.exec(select(Repository).where(Repository.id.in_(ids))).all()
    for repository in repositories:
        repository.last_accessed_at = now
    db.commit()
    return len(repositories)


def _clone_path(repository_id: int) -> Path:
    """The clone directory for a repository id, confined to the storage root.

    The id is coerced to `int` so nothing caller-supplied can reach the path,
    and the result is verified to sit directly inside the root before any
    deletion is attempted.
    """
    root = Path(REPOSITORY_STORAGE_ROOT).resolve()
    target = (root / str(int(repository_id))).resolve()
    if target.parent != root:
        raise ValueError(f"refusing to touch {target}: not inside {root}")
    return target


def _directory_size(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def delete_repository(repository_id: int, db: Session) -> bool:
    """Remove one repository's clone, its chunks, and its row.

    Order matters. The directory goes first: if that fails (permissions, a file
    held open) the database rows survive, so the next sweep retries. The
    reverse order would strand chunks that nothing points at any more.

    Returns True when the repository is gone, False when the removal should be
    retried later.
    """
    target = _clone_path(repository_id)
    freed_bytes = _directory_size(target)

    try:
        if target.exists():
            shutil.rmtree(target)
    except OSError as error:
        logger.warning(
            "could not remove clone for repository %s (%s); keeping rows to retry",
            repository_id,
            error,
        )
        return False

    chunks = db.exec(
        select(CodeChunk).where(CodeChunk.repository_id == repository_id)
    ).all()
    for chunk in chunks:
        db.delete(chunk)

    repository = db.get(Repository, repository_id)
    if repository is not None:
        db.delete(repository)
    db.commit()

    logger.info(
        "expired repository %s: %s chunks, %.1f KiB of clone",
        repository_id,
        len(chunks),
        freed_bytes / 1024,
    )
    return True


def find_expired_repositories(db: Session, ttl_hours: int) -> list[int]:
    """Ids idle for longer than the TTL that are safe to delete.

    `processing` is excluded: a repository mid-index has live handles into its
    own clone and an open transaction against its own rows, so deleting it
    leaves a half-written index and a status nobody can finish.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    repositories = db.exec(
        select(Repository).where(
            Repository.last_accessed_at < cutoff,
            Repository.status != RepositoryStatus.processing,
        )
    ).all()
    return [repository.id for repository in repositories]


def sweep_once(db: Session, ttl_hours: int) -> list[int]:
    """Delete every idle repository past the TTL. Returns the ids removed."""
    with cleanup_lock(db) as acquired:
        if not acquired:
            logger.debug("cleanup skipped: lock held by another process")
            return []

        removed = []
        for repository_id in find_expired_repositories(db, ttl_hours):
            if delete_repository(repository_id, db):
                removed.append(repository_id)
        return removed
