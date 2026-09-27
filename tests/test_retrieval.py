from sqlmodel import Session

from app.db.db import engine
from app.services.retrieval_service import retrieve_code


def evaluate_retrieval(
    question: str,
    repository_id: int,
    expected_files: list[str],
    db,
    top_k: int = 5,
):
    results = retrieve_code(
        query=question,
        repository_id=repository_id,
        db=db,
        top_k=top_k,
    )

    retrieved_files = {
        result["file_path"]
        for result in results
    }

    matched = any(
        file in retrieved_files
        for file in expected_files
    )

    return {
        "question": question,
        "retrieved_files": list(retrieved_files),
        "expected_files": expected_files,
        "hit": matched,
    }


if __name__ == "__main__":
    with Session(engine) as db:
        result = evaluate_retrieval(
            question="Where is user authentication implemented?",
            repository_id=1,
            expected_files=[
                "app/services/auth.py"
            ],
            db=db,
        )

    print(result)