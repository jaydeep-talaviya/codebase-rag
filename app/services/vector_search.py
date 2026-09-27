from sqlmodel import Session, select

from app.models.code_chunk import CodeChunk
from app.services.embedding_service import create_embedding


def keyword_search(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
):
    statement = (
        select(CodeChunk)
        .where(
            CodeChunk.repository_id == repository_id,
            CodeChunk.content.ilike(f"%{query}%"),
        )
        .limit(top_k)
    )

    return db.exec(statement).all()

def search_code(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
):
    query_embedding = create_embedding(query)
    if repository_id is not None:
        statement = (
            select(CodeChunk)
            .where(
                CodeChunk.repository_id == repository_id
            )
            .order_by(
                CodeChunk.embedding.cosine_distance(
                    query_embedding
                )
            )
            .limit(top_k)
        )
    else:
        statement = (
            select(CodeChunk)
            .order_by(
                CodeChunk.embedding.cosine_distance(
                    query_embedding
                )
            )
            .limit(top_k)
        )
    return db.exec(statement).all()


def hybrid_search(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
):
    vector_results = search_code(
        query=query,
        repository_id=repository_id,
        db=db,
        top_k=top_k,
    )

    keyword_results = keyword_search(
        query=query,
        repository_id=repository_id,
        db=db,
        top_k=top_k,
    )

    combined = {}

    for chunk in vector_results + keyword_results:
        combined[chunk.id] = chunk

    return list(combined.values())[:top_k]