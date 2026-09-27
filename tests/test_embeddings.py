from app.services.embedding_service import create_embedding


def test_embedding_dimension():
    vector = create_embedding(
        "def authenticate_user(): pass"
    )

    assert len(vector) == 384