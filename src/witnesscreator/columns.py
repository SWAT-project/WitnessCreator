"""Column heuristics over Java source lines.

Columns are 1-based and count every character (a tab is one column), as the
witness format defines them. The heuristics work on lines whose comments and
string/char literals were blanked out by :func:`mask_non_code`, so a ``nondet(``
inside a comment or a ``)`` inside a string does not confuse them.
"""

from __future__ import annotations

import re
from typing import Optional

NONDET_CALL = re.compile(r"\bnondet[A-Za-z0-9_]*\s*\(")
ASSERT_KEYWORD = re.compile(r"\bassert\b")
THROW_KEYWORD = re.compile(r"\bthrow\b")


def _blank(s: str) -> str:
    return "".join(ch if ch in "\r\n" else " " for ch in s)


def mask_non_code(text: str) -> str:
    """Replaces comments and string/char literals by spaces, keeping every position.

    Line breaks are kept so that line numbers and columns of the result equal those
    of the input. Text blocks (``\"\"\"``) and block comments may span lines.
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = i
            while j < n and text[j] not in "\r\n":
                j += 1
            out.append(" " * (j - i))
            i = j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(_blank(text[i:j]))
            i = j
        elif c == '"' and text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
            out.append(_blank(text[i:j]))
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] not in "\r\n":
                if text[j] == "\\":
                    j += 1
                j += 1
            if j < n and text[j] == c:
                j += 1
            out.append(_blank(text[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def nondet_call_column(line: str, call_index: int) -> Optional[int]:
    """The column of the closing parenthesis of the ``call_index``-th ``nondet*(`` call.

    ``line`` should be a masked line (see :func:`mask_non_code`). ``None`` if the
    line has no such call or its parentheses are unbalanced.
    """
    if line is None or call_index is None or call_index < 0:
        return None
    matches = list(NONDET_CALL.finditer(line))
    if call_index >= len(matches):
        return None
    open_paren = matches[call_index].end() - 1
    depth = 0
    for i in range(open_paren, len(line)):
        ch = line[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _is_java_identifier_part(ch: str) -> bool:
    return ch.isalnum() or ch in "_$"


def _skip_whitespace(line: str, i: int) -> int:
    while i < len(line) and line[i].isspace():
        i += 1
    return i


def statement_column(line: str, assertion: bool) -> Optional[int]:
    """The column of the first character of the violating statement on the line.

    The ``assert`` of a failed assertion, the ``throw`` of an explicit throw,
    otherwise the first token that is not a brace or an ``else``. ``line`` should
    be a masked line (see :func:`mask_non_code`).
    """
    if line is None:
        return None
    if assertion:
        m = ASSERT_KEYWORD.search(line)
        if m:
            return m.start() + 1
    m = THROW_KEYWORD.search(line)
    if m:
        return m.start() + 1
    i = _skip_whitespace(line, 0)
    while i < len(line):
        if line[i] in "{}":
            i = _skip_whitespace(line, i + 1)
        elif line.startswith("else", i) and (
            i + 4 == len(line) or not _is_java_identifier_part(line[i + 4])
        ):
            i = _skip_whitespace(line, i + 4)
        else:
            break
    return i + 1 if i < len(line) else None
