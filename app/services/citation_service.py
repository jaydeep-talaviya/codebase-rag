def build_sources(chunks: list[dict]) -> list[dict]:
    """Cite only the chunks the model actually received.

    Callers must pass the post-rerank list. Including a chunk here that was
    never in the prompt makes the citation a lie, and duplicates are collapsed
    because a file can legitimately be cited by several overlapping chunks.
    """
    sources: list[dict] = []
    seen: set[tuple] = set()

    for chunk in chunks:
        source = {
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
        }
        language = chunk.get("language")
        if language:
            source["language"] = language

        key = (
            source["file_path"],
            source["start_line"],
            source["end_line"],
        )
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)

    return sources
