from sqlmodel import Session, delete

from app.models.code_chunk import CodeChunk


def store_chunks(
    repository_id: int,
    chunks: list[dict],
    db: Session,
):
    # Re-indexing must replace, not append. Ingestion is reachable repeatedly
    # (and runs on a GET), so without this every re-run doubled the chunk count
    # and skewed every search result with duplicates.
    db.execute(
        delete(CodeChunk).where(CodeChunk.repository_id == repository_id)
    )

    code_chunks = []

    for chunk in chunks:
        code_chunk = CodeChunk(
            repository_id=repository_id,
            file_path=chunk["file_path"],
            file_name=chunk["file_name"],
            language=chunk["language"],
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            start_line=chunk["start_line"],
            end_line=chunk["end_line"],
            embedding=chunk["embedding"],
        )

        code_chunks.append(code_chunk)

    db.add_all(code_chunks)
    db.commit()

    return code_chunks