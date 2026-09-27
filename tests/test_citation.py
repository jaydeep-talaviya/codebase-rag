from app.services.citation_service import build_sources


def test_build_sources():
    chunks = [
        {
            "file_path": "app/auth.py",
            "start_line": 10,
            "end_line": 20,
        }
    ]

    sources = build_sources(chunks)

    assert sources == [
        {
            "file_path": "app/auth.py",
            "start_line": 10,
            "end_line": 20,
        }
    ]