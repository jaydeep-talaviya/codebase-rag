from sqlmodel import Session, select

from app.models.code_chunk import CodeChunk
from app.services.embedding_service import create_embedding

# Reciprocal Rank Fusion damping constant, from the original RRF paper. Large
# values flatten the contribution curve so a top-1 hit cannot be overwhelmed by
# several mediocre ones, which is what makes the fusion robust when the two
# rankings disagree.
_RRF_K = 60

# Upper bound on rows pulled for keyword ranking before it is trimmed to top_k.
KEYWORD_CANDIDATE_LIMIT = 200


def escape_like(term: str) -> str:
    """Escape LIKE metacharacters so they match literally.

    `query` is user input interpolated straight into the pattern, so a literal
    `%` or `_` in a search term is currently a wildcard — searching for `50%`
    matches everything. Without an `ESCAPE` clause the backslashes below are
    not honoured either, hence passing one explicitly.
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def keyword_search(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
):
    pattern = f"%{escape_like(query)}%"

    conditions = [CodeChunk.content.ilike(pattern, escape="\\")]
    # `== None` compiles to `IS NULL`, which matches no repository at all, so an
    # unfiltered (cross-repository) search silently lost its keyword half.
    if repository_id is not None:
        conditions.append(CodeChunk.repository_id == repository_id)

    # Ordering happens in Python. There is no single SQL spelling of "position
    # of substring" that works on both engines this runs on — Postgres has
    # `strpos`, SQLite has `instr`, and Postgres has no `instr` — so ranking in
    # SQL meant a function that broke whichever database the other tests used.
    # The fetch is bounded so this cannot become a full table scan.
    statement = (
        select(CodeChunk)
        .where(*conditions)
        .limit(KEYWORD_CANDIDATE_LIMIT)
    )
    hits = list(db.exec(statement).all())

    needle = query.lower()
    # Earlier match first, then the shorter chunk, which is the more focused one.
    hits.sort(
        key=lambda chunk: (
            chunk.content.lower().find(needle),
            len(chunk.content),
        )
    )
    return hits[:top_k]


def search_code(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
):
    query_embedding = create_embedding(query)

    conditions = []
    if repository_id is not None:
        conditions.append(CodeChunk.repository_id == repository_id)

    statement = (
        select(CodeChunk)
        .where(*conditions)
        .order_by(CodeChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return db.exec(statement).all()


def _fuse(rankings: list[list]) -> list:
    """Reciprocal Rank Fusion over several ranked lists of the same rows.

    Rank-based, so it does not need the two sides' scores to be comparable —
    cosine distance and a keyword hit are not on the same scale.
    """
    scores: dict = {}
    by_id: dict = {}

    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (_RRF_K + rank)
            by_id.setdefault(chunk.id, chunk)

    return [by_id[cid] for cid in sorted(scores, key=lambda c: -scores[c])]


def hybrid_search(
    query: str,
    repository_id: int,
    db: Session,
    top_k: int = 5,
    candidates_per_list: int = 4,
):
    """Combine vector and keyword retrieval.

    This used to concatenate the two result sets and truncate to `top_k`, which
    made the keyword half dead code: vector results were inserted first, so a
    full vector result set consumed the entire budget and every keyword hit was
    discarded before it was ever read.

    Both sides are now over-fetched and fused by rank, so each can contribute
    and a chunk found by both is promoted above one found by a single method.
    """
    pool = top_k * candidates_per_list

    vector_results = search_code(
        query=query,
        repository_id=repository_id,
        db=db,
        top_k=pool,
    )

    keyword_results = keyword_search(
        query=query,
        repository_id=repository_id,
        db=db,
        top_k=pool,
    )

    return _fuse([vector_results, keyword_results])[:top_k]
