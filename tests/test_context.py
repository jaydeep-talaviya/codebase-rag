from app.services.context_service import build_context


def test_build_context():
    chunks = [
        {
            "file_path": "app/auth.py",
            "start_line": 10,
            "end_line": 20,
            "language": "python",
            "content": "def authenticate_user(): pass",
        }
    ]

    context = build_context(chunks)

    assert "app/auth.py" in context
    assert "10-20" in context
    assert "authenticate_user" in context