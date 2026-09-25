from fastapi import APIRouter, Depends
from app.db.db import get_session
from app.services.repository import save_repository, get_repository, get_all_repositories
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