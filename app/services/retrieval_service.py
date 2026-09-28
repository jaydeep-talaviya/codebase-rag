from sqlmodel import Session

from app.services.paths import repo_relative_path
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
            # Rows indexed before paths were stored relative still carry the
            # storage prefix. Normalising here — the single chokepoint every
            # downstream reader shares — keeps the prompt and the citations
            # free of the server's directory layout.
            "file_path": repo_relative_path(chunk.file_path, repository_id),
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language,
        }
        for chunk in chunks
    ]