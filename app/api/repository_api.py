from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.db import get_session
from app.services.cleanup import touch_repositories
from app.services.repository import (save_repository, get_repository,
                                get_repository_summaries, get_repository_summary,
                                process_repository, get_cleaned_repository_files,
                                get_repository_file_content)
from app.services.rag_service import ask_repository
from app.representations.repository import AskRequest, RepositoryRepresentation

router = APIRouter(prefix="/repositories")

# Every route here that changes state is a POST, including indexing and asking.
# They used to be `GET`, which was wrong in three separate ways:
#
#   * A `GET` that writes ~300 rows and runs the embedder is not safe to
#     prefetch, cache, or retry. A browser restoring a tab could re-trigger a
#     multi-minute index.
#   * `/search` was the worst of them. It calls an LLM, so every crawl,
#     bookmark restore, or history entry re-read cost real money, and it
#     refreshed the repository's idle timer, so a link someone followed once
#     silently kept a repository alive.
#   * Nothing about a mutation should be reachable by a safe verb.
#
# The genuinely read-only routes below (`GET /`, `GET /{id}/files/{path}`) are
# untouched, because a file preview is a real read.

@router.post("/", response_model=RepositoryRepresentation)
def add_repository(url: str, db: Session = Depends(get_session)):
    existing_repo = get_repository(url,db)
    if existing_repo:
        return existing_repo
    new_repo = save_repository(url,db)
    return new_repo

@router.get("/",response_model=list[RepositoryRepresentation])
def get_repositories(db: Session = Depends(get_session)):
    """Every repository ever uploaded, newest first — the history list.

    Chunk counts come from one grouped query rather than a count per
    repository, so the cost does not grow with the number of repositories.

    Deliberately does not refresh `last_accessed_at`. The frontend loads this
    list to render the page, so treating a read as "use" would keep every
    repository alive forever and nothing would ever be reclaimed.
    """
    return get_repository_summaries(db)

# Declared before `/{repository_id}`. Note that a `GET /repositories/search` is
# still caught by that id route and rejected as a non-integer id (422) rather
# than the 405 a wrong verb would ideally produce. That is harmless: nothing
# mutates, and the alternative is a route declared solely to refuse a verb.
@router.post("/search")
def search_repositories(payload: AskRequest, db: Session = Depends(get_session)):
    return _ask(payload, db)

@router.get("/{repository_id}", response_model=RepositoryRepresentation)
def read_repository(repository_id: int, db: Session = Depends(get_session)):
    """One repository with its chunk count. Read-only, so no idle touch: the
    history list and this route serve the same information."""
    return get_repository_summary(repository_id, db)

@router.post("/{repository_id}/ingest", response_model=RepositoryRepresentation)
def ingest_repository_by_url(repository_id: int, db: Session = Depends(get_session)):
    """Clone the repository. Cheap and idempotent, but still a write."""
    touch_repositories(db, [repository_id])
    return process_repository(repository_id, db)

@router.post("/{repository_id}/index")
def index_repository(repository_id: int, db: Session = Depends(get_session)):
    """Parse, chunk, embed, store. The expensive half of ingestion."""
    touch_repositories(db, [repository_id])
    return get_cleaned_repository_files(repository_id, db)

@router.post("/{repository_id}/ask")
def ask_repository_by_id(repository_id: int, payload: AskRequest, db: Session = Depends(get_session)):
    return _ask(payload.model_copy(update={"repository_id": repository_id}), db)

@router.get("/{repository_id}/files/{file_path:path}")
def read_repository_file(
    repository_id: int, file_path: str, db: Session = Depends(get_session)
):
    """Real file contents, so a citation can show code instead of coordinates.

    The only `GET` left under a repository besides the list: it reads a file
    from the clone and changes nothing. Path traversal is rejected in
    `repository.resolve_repository_file`.
    """
    touch_repositories(db, [repository_id])
    return get_repository_file_content(repository_id, file_path)


def _ask(payload: AskRequest, db: Session):
    # Only an explicit repository_id counts as use. A cross-repository search
    # would otherwise wake every stored repository on every keystroke.
    touch_repositories(db, [payload.repository_id])
    return ask_repository(
        question=payload.question,
        repository_id=payload.repository_id,
        db=db,
    )
