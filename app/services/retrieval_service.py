from sqlmodel import Session

from app.services.vector_search import hybrid_search

def retrieve_code(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
):
    chunks = hybrid_search(
        query=query,
        repository_id=repository_id,
        db=db,
        top_k=top_k,
    )

    return [
        {
            "content": chunk.content,
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
        }
        for chunk in chunks
    ]