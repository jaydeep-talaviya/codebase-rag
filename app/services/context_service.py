def build_context(
    chunks: list[dict],
    max_chunks: int = 5,
) -> str:

    chunks = chunks[:max_chunks]

    context_parts = []

    for chunk in chunks:
        context_parts.append(
            f"""File: {chunk["file_path"]}
            Lines: {chunk["start_line"]}-{chunk["end_line"]}

            ```{chunk["language"]}
            {chunk["content"]}
            ```"""
        )

    return "\n\n".join(context_parts)