from app.models.repository import Repository, RepositoryStatus
from app.models.code_chunk import CodeChunk
from app.config import settings
from app.representations.repository import RepositoryRepresentation
from sqlmodel import func, select
import re
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
import subprocess
import os
from pathlib import Path
from pygments.lexers import get_lexer_for_filename
from app.services.paths import REPOSITORY_STORAGE_ROOT
from app.services.code_parser import get_cleaned_files
from app.services.code_chunker import chunk_code
from app.services.embedding_service import create_embeddings, embeddable_text
from app.services.symbols import extract_symbols
from app.services.vector_storage import store_chunks

MAX_PREVIEW_BYTES = 1_000_000
# A run that dies mid-index leaves `processing` behind with nobody to finish it.
# Past this age the row is treated as abandoned and indexing may be resumed.
PROCESSING_STALE_AFTER = timedelta(minutes=30)

def get_repo_name(url: str,db=None):
    name = url.split("/")[-1]
    return name


def is_valid_github_url(url: str) -> bool:
    """Check if URL matches a valid GitHub URL pattern."""
    pattern = r'^https?://github\.com/[\w-]+/[\w.-]+/?$'
    return bool(re.match(pattern, url))   

def save_repository(url: str, db=None):
    if not is_valid_github_url(url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")
    name = get_repo_name(url,db)
    repository = Repository(url=url, name=name, status="pending")
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository

def get_repository(url: str, db=None):
    return db.query(Repository).filter(Repository.url == url).first()

def get_all_repositories(db=None):
    return db.query(Repository).order_by(Repository.created_at.desc()).all()

def get_repository_summaries(db=None):
    """Repositories plus their searchable chunk count, newest first.

    One grouped query for every count, instead of a per-repository COUNT,
    so listing history stays flat as the number of repositories grows.
    """
    repositories = get_all_repositories(db)

    counts = dict(
        db.execute(
            select(CodeChunk.repository_id, func.count())
            .group_by(CodeChunk.repository_id)
        ).all()
    )

    return [
        RepositoryRepresentation(
            id=repository.id,
            name=repository.name,
            url=repository.url,
            status=repository.status,
            created_at=repository.created_at,
            last_accessed_at=repository.last_accessed_at,
            # `None` when cleanup is switched off, so the UI does not promise a
            # deadline that nothing will act on.
            expires_at=expiry_for(repository),
            chunk_count=counts.get(repository.id, 0),
        )
        for repository in repositories
    ]


def expiry_for(repository: Repository) -> datetime | None:
    """When this repository becomes eligible for the sweeper to delete it.

    This is when it crosses the idle threshold, not when it is actually removed
    — the sweeper runs on an interval, so there is up to
    `repo_cleanup_interval_minutes` of lag after this moment.
    """
    if not settings.repo_cleanup_enabled:
        return None

    last = repository.last_accessed_at
    if last is None:
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last + timedelta(hours=settings.repo_idle_ttl_hours)

def mark_processing(repository: Repository) -> Repository:
    """Stamp `updated_at` so an interrupted run can be told from a live one."""
    repository.status = RepositoryStatus.processing
    repository.updated_at = datetime.now(timezone.utc)
    return repository


def is_abandoned_processing(repository: Repository) -> bool:
    last_touch = repository.updated_at
    if last_touch is None:
        return True
    if last_touch.tzinfo is None:
        last_touch = last_touch.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_touch > PROCESSING_STALE_AFTER


def sub_process_repository(repository: Repository, db=None):
    target_folder = get_repository_root(repository.id)
    # Re-running ingest on an already-cloned repository must not fail on
    # "destination path already exists"; the clone is the cheap, idempotent
    # half of ingestion, indexing is the expensive half.
    if not (target_folder / ".git").is_dir():
        target_folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", repository.url, str(target_folder)], check=True)
    # Status stays `processing` here. Cloning is not ingestion — nothing is
    # searchable yet, so claiming `completed` is what made a failed index
    # look like a successful one.
    return repository
    
def process_repository(repository_id: int, db=None):
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repository.status == RepositoryStatus.processing and not is_abandoned_processing(repository):
        raise HTTPException(status_code=400, detail="Repository is already being processed")
    print(f"Processing repository: {repository.status} with ID: {repository.id}")
    # Process the repository (e.g., clone it, analyze it, etc.)
    mark_processing(repository)
    try:
        repository = sub_process_repository(repository,db)
    except Exception as e:
        repository.status = RepositoryStatus.failed
        db.commit()
        db.refresh(repository)
        raise HTTPException(status_code=500, detail=str(e))
    db.commit()
    db.refresh(repository)
    return repository

def get_cleaned_repository_files(repository_id: int, db=None):
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    target_folder = get_repository_root(repository.id)
    # Precondition, not a processing failure: nothing was cloned yet, so leave
    # the status alone and let the caller run the clone step first. Without
    # this, `os.walk` over a missing directory yields nothing and the run
    # "succeeds" with zero chunks and a `completed` status.
    if not (target_folder / ".git").is_dir():
        raise HTTPException(
            status_code=409,
            detail="Repository has not been cloned yet. Run the ingest step first.",
        )

    # `completed` is only honest once chunks are actually in the database.
    mark_processing(repository)
    db.commit()
    try:
        files = get_cleaned_files(str(target_folder),repository_id)
        chunks = [chunk for file in files for chunk in chunk_code(file)]

        if not chunks:
            raise ValueError(
                "No indexable text files were found in this repository."
            )

        # The embedded text carries the path and the chunk's defined symbols;
        # the stored `content` stays verbatim so citations show real code.
        embeddings = create_embeddings(
            [
                embeddable_text(chunk["file_path"], chunk["content"], extract_symbols(chunk["content"]))
                for chunk in chunks
            ]
        )
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        store_chunks(repository.id, chunks, db)
    except Exception as e:
        repository.status = RepositoryStatus.failed
        db.commit()
        db.refresh(repository)
        raise HTTPException(status_code=500, detail=str(e))

    repository.status = RepositoryStatus.completed
    db.commit()
    db.refresh(repository)
    return files


def get_repository_root(repository_id: int) -> Path:
    return (Path(REPOSITORY_STORAGE_ROOT) / str(repository_id)).resolve()


def resolve_repository_file(repository_id: int, file_path: str) -> Path:
    """Map a citation path onto a real file inside the repository clone.

    Citations store paths as `data/repositories/{id}/...`; callers may send that
    form or a repo-relative one, so both are accepted. The resolved path is
    then confined to the clone — without that check `{file_path:path}` would
    happily serve `/etc/passwd` or `../../.env` to anyone who can reach the API.
    """
    root = get_repository_root(repository_id)
    relative = file_path.replace("\\", "/")

    for prefix in (f"{REPOSITORY_STORAGE_ROOT}/{repository_id}/", root.as_posix() + "/"):
        if relative.startswith(prefix):
            relative = relative[len(prefix):]
            break

    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return target


def get_repository_file_content(repository_id: int, file_path: str):
    root = get_repository_root(repository_id)
    target = resolve_repository_file(repository_id, file_path)

    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found in this repository")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="File is not UTF-8 text")
    except OSError as error:
        raise HTTPException(status_code=500, detail=str(error))

    if len(content) > MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="File is too large to preview")

    try:
        language = get_lexer_for_filename(target.name).name
    except Exception:
        language = "unknown"

    return {
        # Repo-relative, matching what citations carry. The caller already
        # knows the repository id, so the storage prefix is pure noise.
        "file_path": target.relative_to(root).as_posix(),
        "language": language,
        "content": content,
        "line_count": content.count("\n") + 1 if content else 0,
    }
