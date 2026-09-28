"""Pull the names a chunk defines, so definition lookups can hit the right chunk.

A question like "where is `get_repository_root` defined" embeds to a vector that
sits closest to whichever chunk *mentions* the name most often — often a
call site, an import, or a docstring — rather than the chunk that declares it.
Feeding the declared names into the embedded text gives the retriever an
explicit "this chunk defines X" signal.

Deliberately regex-based and language-agnostic rather than a real parser: the
goal is a cheap, never-throwing hint, not a correct syntax tree. A missed
symbol costs a slightly worse ranking; a raised exception would cost the whole
indexing run.
"""
import re

# Language keywords sit behind modifiers, so `class Widget` and
# `export class Widget` must both match. `^\s*class` alone silently missed every
# exported class, which is most classes in a TypeScript codebase.
_MODIFIERS = (
    r"(?:export\s+|default\s+|public\s+|private\s+|protected\s+|internal\s+"
    r"|static\s+|abstract\s+|final\s+|override\s+|async\s+|pub\s+|open\s+)*"
)

# Ordered so the more specific forms are tried before the general ones. Every
# group that can capture a name does so in group 1.
_PATTERNS = (
    re.compile(rf"^\s*{_MODIFIERS}(?:async\s+)?def\s+(\w+)"),                     # python
    re.compile(rf"^\s*{_MODIFIERS}class\s+(\w+)"),                              # py/java/js/ts/rust
    re.compile(rf"^\s*{_MODIFIERS}function\s*\*?\s*(\w+)"),                     # js/ts
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*[:=]\s*(?:async\s*)?\("),
    re.compile(r"^\s*(?:pub\s+)?func\s+(\w+)"),                                 # go
    re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(\w+)"),          # rust
    re.compile(r"^\s*(?:pub\s+)?(?:struct|enum|trait|interface)\s+(\w+)"),
    re.compile(r"^\s*type\s+(\w+)"),                                             # go type alias
    re.compile(r"^\s*module\s+(\w+)"),                                           # terraform
    re.compile(r"^\s*(?:public|private|protected|static|final|abstract|override|\s)+"
               r"[\w<>\[\],.]+\s+(\w+)\s*\([^;{]*\)\s*[{;]"),                     # java/c/cpp
)

# Keywords that match the C-style method pattern but are not identifiers.
_NOT_SYMBOLS = frozenset(
    {"if", "for", "while", "switch", "catch", "return", "else", "do", "try"}
)

# A chunk is ~1000 characters, so this is a generous ceiling, but a file that
# is one long enum or lookup table can define hundreds of names. Past a certain
# point the list stops being a signal and just dilutes the embedding.
MAX_SYMBOLS = 40


def extract_symbols(content: str) -> list[str]:
    """Return the unique definition names in `content`, in source order."""
    found: list[str] = []
    seen: set[str] = set()

    for line in content.splitlines():
        # Every pattern is tried on every line. A keyword pre-filter was tried
        # here for speed and was wrong: it skipped `const x = () => {}` because
        # that line contains none of the definition keywords, silently dropping
        # every arrow function. Chunks are ~1000 characters, so running ten
        # cheap regexes per line is not worth that risk.
        for pattern in _PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            name = match.group(1)
            if not name or name in _NOT_SYMBOLS or name in seen:
                continue
            seen.add(name)
            found.append(name)
            break
        if len(found) >= MAX_SYMBOLS:
            break

    return found
