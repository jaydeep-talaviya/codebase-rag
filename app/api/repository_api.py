from fastapi import APIRouter, Depends
from app.db.db import get_session
from app.services.repository import (save_repository, get_repository, 
                                get_all_repositories, process_repository,
                                get_cleaned_repository_files)
from app.services.vector_search import search_code
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
    repositories = get_all_repositories(db)
    return repositories

@router.get("/{repository_id}/ingest", response_model=RepositoryRepresentation)
def ingest_repository_by_url(repository_id: int, db: Session = Depends(get_session)):
    return process_repository(repository_id, db)

@router.get("/{repository_id}/files")
def get_cleaned_repository(repository_id: int, db: Session = Depends(get_session)):
    return get_cleaned_repository_files(repository_id, db)

@router.get("/search")
def ask_question(query: str, repository_id: int=None, db: Session = Depends(get_session)):
    results = search_code(
        query=query,
        repository_id=repository_id,
        db=db,
        top_k=5,
    )
    for result in results:
        print(
            result.file_path,
            result.start_line,
            result.end_line,
        )
    return results