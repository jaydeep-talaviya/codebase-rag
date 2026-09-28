from sqlmodel import Session

from app.services.retrieval_service import retrieve_code
from app.services.reranker import rerank
from app.services.context_service import build_context
from app.services.llm_service import generate_answer
from app.services.citation_service import build_sources


def ask_repository(
    question: str,
    repository_id: int,
    db: Session,
    top_k: int = 20,
    rerank_top_k: int = 5,
):
    chunks = retrieve_code(
        query=question,
        repository_id=repository_id,
        db=db,
        top_k=top_k,
    )
    reranked_chunks = rerank(
        query=question,
        chunks=chunks,
        top_k=rerank_top_k,
    )

    context = build_context(reranked_chunks)

    answer = generate_answer(
        question=question,
        context=context,
    )
    # Cite the reranked chunks, not the pre-rerank pool: only `reranked_chunks`
    # ever reached build_context, so citing `chunks` attributed the answer to
    # 15 passages the model never saw.
    sources = build_sources(reranked_chunks)

    return {
        "answer": answer,
        "sources": sources,
    }
