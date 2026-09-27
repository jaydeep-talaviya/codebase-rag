from app.services.code_chunker import chunk_code


def test_chunk_code():
    parsed_file = {
        "file_path": "test.py",
        "file_name": "test.py",
        "language": "python",
        "content": "def hello():\n    return 'hello'\n",
    }

    chunks = chunk_code(parsed_file)

    assert len(chunks) > 0
    assert chunks[0]["file_path"] == "test.py"
    assert chunks[0]["language"] == "python"
    assert chunks[0]["content"]