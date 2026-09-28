"""One definition of where repositories live on disk.

Ingestion used to store the full on-disk path (`data/repositories/{id}/src/App.js`)
in `code_chunks.file_path`. That string then leaked everywhere: into the prompt
sent to the LLM, into every citation, and into the UI. Nothing outside this
module should know the storage layout.
"""

import os
import re

REPOSITORY_STORAGE_ROOT = "data/repositories"

# Anchored so a bare `data/repositories` (no id) is never rewritten, and the
# group is lazy: only the forms that actually carry a repository id are tried.
_STORAGE_PREFIX = re.compile(
    r"^(?:\./)?" + re.escape(REPOSITORY_STORAGE_ROOT) + r"/(?P<relative>.*)$"
)
_ABSOLUTE_PREFIX = re.compile(
    r"^" + re.escape(os.path.abspath(REPOSITORY_STORAGE_ROOT)) + r"/(?P<relative>.*)$"
)
_REPOSITORY_SEGMENT = re.compile(r"^(?P<repository_id>\d+)(?=/|$)")


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

    match = _STORAGE_PREFIX.match(normalized) or _ABSOLUTE_PREFIX.match(normalized)
    if match is None:
        return normalized

    remainder = match.group("relative")

    if repository_id is not None:
        segment = _REPOSITORY_SEGMENT.match(remainder)
        # A leading `<n>/` belongs to the storage layout only when it matches
        # the repository we are resolving for; otherwise it is a real directory.
        if segment and int(segment.group("repository_id")) != repository_id:
            return normalized

    return remainder

