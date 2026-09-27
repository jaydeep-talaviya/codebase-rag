from app.models.repository import Repository, RepositoryStatus
import re
from fastapi import HTTPException
import subprocess
import os
from app.services.code_parser import get_cleaned_files
from app.services.code_chunker import chunk_code
from app.services.embedding_service import create_embeddings
from app.services.vector_storage import store_chunks

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

def sub_process_repository(repository: Repository, db=None):
    target_folder = f"data/repositories/{repository.id}"
    os.makedirs(target_folder, exist_ok=True)
    # Clone the repository
    subprocess.run(["git", "clone", repository.url, target_folder], check=True)
    repository.status = RepositoryStatus.completed
    return repository
    
def process_repository(repository_id: int, db=None):
    repository = db.query(Repository).filter(Repository.id == repository_id).first()
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repository.status == RepositoryStatus.processing:
        raise HTTPException(status_code=400, detail="Repository is already being processed")
    if repository.status == RepositoryStatus.completed:
        raise HTTPException(status_code=400, detail="Repository has already been processed")
    print(f"Processing repository: {repository.status} with ID: {repository.id}")
    # Process the repository (e.g., clone it, analyze it, etc.)
    repository.status = RepositoryStatus.processing
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
    target_folder = f"data/repositories/{repository.id}"
    files = get_cleaned_files(target_folder,repository_id)
    chunks = [chunk for file in files for chunk in chunk_code(file)]

    embeddings = create_embeddings([chunk["content"] for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding

    store_chunks(repository.id, chunks, db)
    return files
