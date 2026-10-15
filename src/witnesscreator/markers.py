"""The legacy ``[WITNESS]`` / ``[WITNESS_TARGET]`` marker lines SWAT printed.

Each marker is followed by the base64 of its payload:

* ``[WITNESS]``: ``value@@@line@@@class@@@methodDesc@@@callIndex@@@typeDesc@@@sourceFile``
  (the 4-field form ``value@@@line@@@class@@@methodDesc`` is still accepted);
  because a String value may contain the separator, fields are parsed from the end;
* ``[WITNESS_TARGET]``: ``throwable@@@class@@file@@line;class@@file@@line;...``
  (innermost frame first).
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from typing import Iterable, List, Optional, Tuple

from .model import Frame, Location, NondetReturn, Violation, normalize_type

log = logging.getLogger("witnesscreator")

VALUE_MARKER = "[WITNESS]"
TARGET_MARKER = "[WITNESS_TARGET]"
SEPARATOR = "@@@"
TYPE_DESCRIPTORS = {"Z", "B", "C", "S", "I", "J", "F", "D", "Ljava/lang/String;"}

_B64_JUNK = re.compile(r"[^A-Za-z0-9+/=_-]")


def decode_base64(text: str) -> str:
    """Decodes base64 (standard or URL-safe, padding optional) to UTF-8 text."""
    s = _B64_JUNK.sub("", str(text).strip()).replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        raw = base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"invalid base64: {e}") from e
    return raw.decode("utf-8", errors="replace")


def _is_int(s: str) -> bool:
    try:
        int(s.strip())
        return True
    except ValueError:
        return False


def function_for_type(type_name: Optional[str]) -> Optional[str]:
    t = normalize_type(type_name)
    if t is None:
        return None
    return "nondet" + t[0].upper() + t[1:]


def parse_value_marker(payload: str) -> NondetReturn:
    """Parses the payload of a ``[WITNESS]`` marker (7- or 4-field form)."""
    parts = payload.split(SEPARATOR)
    n = len(parts)
    if n >= 7 and parts[n - 2].strip() in TYPE_DESCRIPTORS and _is_int(parts[n - 3]) and _is_int(parts[n - 6]):
        type_desc = parts[n - 2].strip()
        return NondetReturn(
            function=function_for_type(type_desc),
            type=normalize_type(type_desc),
            value=SEPARATOR.join(parts[: n - 6]),
            location=Location(
                class_name=parts[n - 5].strip(),
                source_file=parts[n - 1].strip() or None,
                line=int(parts[n - 6].strip()),
                call_index=int(parts[n - 3].strip()),
                method=parts[n - 4].strip() or None,
            ),
        )
    if n >= 4 and _is_int(parts[n - 3]):
        return NondetReturn(
            function=None,
            type=None,
            value=SEPARATOR.join(parts[: n - 3]),
            location=Location(
                class_name=parts[n - 2].strip(),
                source_file=None,
                line=int(parts[n - 3].strip()),
                call_index=0,
                method=parts[n - 1].strip() or None,
            ),
        )
    raise ValueError(f"invalid witness marker: {payload!r}")


def parse_target_marker(payload: str) -> Violation:
    """Parses the payload of a ``[WITNESS_TARGET]`` marker."""
    idx = payload.find(SEPARATOR)
    if idx < 0:
        raise ValueError(f"invalid witness target marker: {payload!r}")
    throwable = payload[:idx].strip()
    frames: List[Frame] = []
    rest = payload[idx + len(SEPARATOR) :].strip()
    if rest:
        for frame in rest.split(";"):
            fields = frame.split("@@")
            if len(fields) != 3:
                continue
            try:
                line = int(fields[2].strip())
            except ValueError:
                line = -1
            frames.append(Frame(fields[0].strip(), fields[1].strip() or None, line))
    return Violation(throwable, frames)


def parse_marker_lines(lines: Iterable[str]) -> Tuple[List[NondetReturn], Optional[Violation]]:
    """Extracts the values and the (last) target from output lines carrying markers.

    Lines without a marker are ignored, so the whole output of a run may be passed.
    Undecodable markers are logged and skipped.
    """
    values: List[NondetReturn] = []
    violation: Optional[Violation] = None
    for raw in lines:
        line = str(raw)
        idx = line.find(TARGET_MARKER)
        if idx >= 0:
            try:
                violation = parse_target_marker(decode_base64(line[idx + len(TARGET_MARKER) :]))
            except ValueError as e:
                log.warning("Ignoring bad target marker (%s): %s", e, line.strip())
            continue
        idx = line.find(VALUE_MARKER)
        if idx >= 0:
            try:
                values.append(parse_value_marker(decode_base64(line[idx + len(VALUE_MARKER) :])))
            except ValueError as e:
                log.warning("Ignoring bad witness marker (%s): %s", e, line.strip())
    return values, violation


def parse_markers(text: str) -> Tuple[List[NondetReturn], Optional[Violation]]:
    """Like :func:`parse_marker_lines` for a block of text, which may itself be base64."""
    if text is None:
        return [], None
    if VALUE_MARKER not in text and TARGET_MARKER not in text and text.strip():
        try:
            decoded = decode_base64(text)
        except ValueError:
            decoded = ""
        if VALUE_MARKER in decoded or TARGET_MARKER in decoded:
            text = decoded
        elif decoded.strip():
            log.warning("No witness markers found in the (decoded) input")
    return parse_marker_lines(text.splitlines())
