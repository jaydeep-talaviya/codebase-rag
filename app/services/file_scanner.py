import os
import re
import fnmatch
from pygments.lexers import get_lexer_for_filename

from app.config import settings

MAX_FILE_SIZE_BYTES = settings.max_file_size_mb * 1024 * 1024

ignore_dirs = [
    "__pycache__",
    "data",
    ".git",
    ".idea",
    ".vscode",
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

def get_cleaned_files(folder_path:str, repository_id:int):
    cleaned_files = []

    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:

            if not is_ignored(file):
                file_path = os.path.join(root, file)

                if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
                    continue

                try:
                    lexer = get_lexer_for_filename(file)
                except Exception:
                    lexer = None
                data = {
                    "repository_id": repository_id,
                    "file_path": file_path,
                    "file_name": file,
                    "extension": os.path.splitext(file)[1],
                    "language": lexer.name if lexer else None
                }
                cleaned_files.append(data)
    print(cleaned_files)
    return cleaned_files