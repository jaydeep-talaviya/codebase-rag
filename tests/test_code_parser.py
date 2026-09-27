from app.services.code_parser import parse_file


def test_parse_file(tmp_path):
    file = tmp_path / "test.py"

    file.write_text(
        "def hello():\n"
        "    return 'hello'\n"
    )

    result = parse_file(str(file), repository_id=1)

    assert result["file_name"] == "test.py"
    assert result["language"] == "Python"
    assert result["start_line"] == 1
    assert result["end_line"] == 2