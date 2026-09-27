from app.services.rag_service import ask_repository


def test_rag_pipeline(monkeypatch, db):

    def fake_generate_answer(question, context):
        return "Authentication is implemented in auth.py."

    monkeypatch.setattr(
        "app.services.rag_service.generate_answer",
        fake_generate_answer,
    )

    result = ask_repository(
        question="How does authentication work?",
        repository_id=1,
        db=db,
    )

    assert "answer" in result
    assert "sources" in result