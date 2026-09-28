import os
import re
import fnmatch
from pygments.lexers import get_lexer_for_filename
from pathlib import Path
from app.config import settings

MAX_FILE_SIZE_BYTES = settings.max_file_size_mb * 1024 * 1024

ignore_dirs = [
    "__pycache__",
    "data",
    ".git",
    ".idea",
    ".vscode",
    "node_modules"
]

ignore_files = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".env",
    ".env.*",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.zip",
    "*.pdf",
    "*.mp4",
    ".vercelignore",
    ".gitignore",
    # Generated dependency manifests. These are enormous, machine-written, and
    # mention every package name in the project, so they match almost any
    # natural-language query while saying nothing about what the code does.
    # Left in, `package-lock.json` alone supplied 3 of the 5 sources for
    # "what does this project do and where is the entry point".
    # `is_ignored` matches the basename only, so these need no path handling.
    "*-lock.json",
    "*-lock.yaml",
    "*.lock",
    "go.sum",
    "npm-shrinkwrap.json",
    # Build output: minified and bundled files are one enormous line, which
    # also defeats the line-based citation maths in the preview.
    "*.min.js",
    "*.min.mjs",
    "*.min.css",
    "*.bundle.js",
    "*.map",
]


def is_ignored(file_path):
    return any(fnmatch.fnmatch(file_path, pattern) for pattern in ignore_files)


def is_binary(file_path: str) -> bool:
    """A NUL byte in the first block is the standard binary tell.

    Cheaper and far more reliable than extending `ignore_files`: the deny-list
    can never cover every extension, and a binary that slips through reaches
    Postgres as text and fails the whole insert with
    "a string literal cannot contain NUL (0x00) characters".
    """
    try:
        with open(file_path, "rb") as handle:
            return b"\x00" in handle.read(8192)
    except OSError:
        return True


def decode_text(file_path: str) -> str | None:
    """Return the file as text, or None if it is not decodable source."""
    if is_binary(file_path):
        return None
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def parse_file(source_path: str, repository_id: int, relative_path: str | None = None):
    """Read `source_path` from disk, but record it as `relative_path`.

    Storing the on-disk path would bake the server's storage layout
    (`data/repositories/{id}/...`) into the database, the LLM prompt and every
    citation, so the two paths are deliberately kept separate.
    """
    content = decode_text(source_path)
    if content is None:
        return None

    lines = content.splitlines()

    try:
        lexer = get_lexer_for_filename(source_path)
    except Exception:
        lexer = None

    data = {
        "repository_id": repository_id,
        "file_path": relative_path or source_path,
        "file_name": os.path.basename(source_path),
        "extension": os.path.splitext(source_path)[1],
        "language": lexer.name if lexer else "unknown",
        "content": content,
        "start_line": 1,
        "end_line": len(lines),
    }
    return data

def get_cleaned_files(folder_path:str, repository_id:int):
    cleaned_files = []

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:

            if not is_ignored(file):
                file_path = os.path.join(root, file)

                if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
                    continue

                relative_path = os.path.relpath(file_path, folder_path)
                parsed = parse_file(file_path, repository_id, relative_path)
                if parsed is not None:
                    cleaned_files.append(parsed)

    return cleaned_files