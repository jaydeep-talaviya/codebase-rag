"""One definition of where repositories live on disk.

Ingestion used to store the full on-disk path (`data/repositories/{id}/src/App.js`)
in `code_chunks.file_path`. That string then leaked everywhere: into the prompt
sent to the LLM, into every citation, and into the UI. Nothing outside this
module should know the storage layout.
"""

import re

REPOSITORY_STORAGE_ROOT = "data/repositories"

# Matches the storage layout in both forms, with any leading directory:
#   data/repositories/7/src/App.js
#   /code/data/repositories/7/src/App.js
# The `<id>` segment is required, so a repository that genuinely contains
# `data/repositories/foo.js` is left alone.
_STORAGE_PREFIX = re.compile(
    r"^(?:.*/)?"
    + re.escape(REPOSITORY_STORAGE_ROOT)
    + r"/(?P<repository_id>\d+)/(?P<relative>.*)$"
)


def repo_relative_path(file_path: str, repository_id: int | None = None) -> str:
    """Return the path as it exists inside the repository.

    `data/repositories/7/src/App.js` -> `src/App.js`
    `/code/data/repositories/7/src/App.js` -> `src/App.js`

    Idempotent: a path that is already relative is returned unchanged, so this
    is safe to apply to rows written before paths were stored relative.
    `repository_id`, when given, is only used to avoid stripping a leading
    `data/repositories/<n>/` that belongs to a different repository.
    """
    if not file_path:
        return file_path

    normalized = file_path.replace("\\", "/")

    match = _STORAGE_PREFIX.match(normalized)
    if match is None:
        return normalized

    if repository_id is not None and int(match.group("repository_id")) != repository_id:
        return normalized

    return match.group("relative")

