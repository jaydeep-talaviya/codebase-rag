from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.db import get_session
from app.services.repository import (save_repository, get_repository, 
                                get_all_repositories, get_repository_summaries,
                                process_repository,
                                get_cleaned_repository_files,
                                get_repository_file_content)
from app.services.rag_service import ask_repository
from app.representations.repository import RepositoryRepresentation

router = APIRouter(prefix="/repositories")

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
    """
    return get_repository_summaries(db)

@router.get("/{repository_id}/ingest", response_model=RepositoryRepresentation)
def ingest_repository_by_url(repository_id: int, db: Session = Depends(get_session)):
    return process_repository(repository_id, db)

@router.get("/{repository_id}/files")
def get_cleaned_repository(repository_id: int, db: Session = Depends(get_session)):
    return get_cleaned_repository_files(repository_id, db)

@router.get("/{repository_id}/files/{file_path:path}")
def read_repository_file(repository_id: int, file_path: str):
    return get_repository_file_content(repository_id, file_path)

@router.get("/search")
def ask_question(query: str, repository_id: int=None, db: Session = Depends(get_session)):
    return ask_repository(
        question=query,
        repository_id=repository_id,
        db=db,
    )