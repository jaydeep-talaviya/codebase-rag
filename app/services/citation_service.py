def build_sources(chunks: list[dict]) -> list[dict]:
    return [
        {
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
        }
        for chunk in chunks
    ]