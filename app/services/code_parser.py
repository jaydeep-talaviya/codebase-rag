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
    ".gitignore"
]


def is_ignored(file_path):
    return any(fnmatch.fnmatch(file_path, pattern) for pattern in ignore_files)


def parse_file(file_path: str, repository_id: int):
    content = Path(file_path).read_text(
        encoding="utf-8",
        errors="ignore",
    )
    lines = content.splitlines()

    try:
        lexer = get_lexer_for_filename(file_path)
    except Exception:
        lexer = None

    data = {
        "repository_id": repository_id,
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "extension": os.path.splitext(file_path)[1],
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

                cleaned_files.append(parse_file(file_path, repository_id))

    return cleaned_files