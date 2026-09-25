from app.models.repository import Repository
import re
from fastapi import HTTPException


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
    return db.query(Repository).all()
