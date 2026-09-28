from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def create_embedding(text: str) -> list[float]:
    return create_embeddings([text])[0]


def create_embeddings(texts: list[str]) -> list[list[float]]:
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
    )

    return embeddings.tolist()


def embeddable_text(file_path: str, content: str, symbols: list[str] | None = None) -> str:
    """Build the text actually sent to the model.

    Embedding the raw chunk alone loses information the retriever needs:

    * **Path.** Two modules can both define `get_repository_root`, and content
      alone cannot tell them apart. Prefixing the path puts file location into
      the vector, so "where is the config read" can reach `app/config.py`.
    * **Symbols.** Makes the chunk that *defines* a name score higher for
      "where is X defined" than the chunks that merely call it.

    Only the embedded text changes. `content` is stored and shown to the user
    verbatim, so citations and previews still show real code rather than this
    decorated header.
    """
    header = f"File: {file_path}"
    if symbols:
        header += f"\nDefines: {', '.join(symbols)}"
    return f"{header}\n\n{content}"