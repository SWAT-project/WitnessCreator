"""Rendering of recorded values as Java literals and ``java_expression`` constraints."""

from __future__ import annotations

import re
import struct
from decimal import Decimal, InvalidOperation
from typing import Optional

from .model import normalize_type

RESULT = "\\result"

_INT_RE = re.compile(r"^[+-]?\d+$")
_INT_MIN, _INT_MAX = -(2**31), 2**31 - 1

_JAVA_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
}

_CHAR_ESCAPES = {
    0x27: "'\\''",
    0x5C: "'\\\\'",
    0x0A: "'\\n'",
    0x0D: "'\\r'",
    0x09: "'\\t'",
    0x08: "'\\b'",
    0x0C: "'\\f'",
}


def result_constraint(value: str, type_name: Optional[str]) -> str:
    """The ``java_expression`` satisfied exactly when the call returned ``value``.

    ``type_name`` is a Java type name (``int``, ``String``, ...) or a JVM descriptor
    (``I``, ``Ljava/lang/String;``); ``None`` selects the legacy rendering that only
    looks at the value (integers and booleans compare with ``==``, everything else is
    a string).
    """
    value = "" if value is None else str(value)
    t = normalize_type(type_name)
    if t is None:
        return _legacy_constraint(value)
    if t == "boolean":
        return f"{RESULT} == {'true' if value.strip() == 'true' else 'false'}"
    if t in ("byte", "short", "int"):
        return f"{RESULT} == {value.strip()}"
    if t == "long":
        return f"{RESULT} == {long_literal(value)}"
    if t == "char":
        return f"{RESULT} == {char_literal(value)}"
    if t == "float":
        return floating_constraint(value, True)
    if t == "double":
        return floating_constraint(value, False)
    return f"{RESULT}.equals({string_literal(value)})"


def _legacy_constraint(value: str) -> str:
    v = value.strip()
    if _INT_RE.match(v) or v in ("true", "false"):
        return f"{RESULT} == {v}"
    return f"{RESULT}.equals({string_literal(value)})"


def long_literal(value: str) -> str:
    """``L`` suffix only when the value does not fit into an ``int``."""
    v = value.strip()
    try:
        n = int(v)
    except ValueError:
        return v
    if _INT_MIN <= n <= _INT_MAX:
        return v
    return f"{v}L"


def char_literal(code_point) -> str:
    """Char values are recorded as their code point; renders the Java char literal."""
    try:
        c = int(str(code_point).strip())
    except ValueError:
        return str(code_point)
    if c < 0 or c > 0xFFFF:
        return str(code_point)
    if c in _CHAR_ESCAPES:
        return _CHAR_ESCAPES[c]
    if 0x20 <= c < 0x7F:
        return f"'{chr(c)}'"
    return f"'\\u{c:04x}'"


def string_literal(value: str) -> str:
    """A Java string literal: every character outside printable ASCII is escaped.

    Characters outside the Basic Multilingual Plane are written as surrogate pairs,
    which is how Java sees them.
    """
    out = ['"']
    for ch in value:
        esc = _JAVA_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
            continue
        c = ord(ch)
        if 0x20 <= c < 0x7F:
            out.append(ch)
        elif c > 0xFFFF:
            c -= 0x10000
            out.append(f"\\u{0xD800 + (c >> 10):04x}\\u{0xDC00 + (c & 0x3FF):04x}")
        else:
            out.append(f"\\u{c:04x}")
    out.append('"')
    return "".join(out)


def plain_decimal(value: str) -> str:
    """``1.0E10`` -> ``10000000000``, ``-0.0`` stays ``-0.0``; unparsable values are kept."""
    v = value.strip()
    if v.endswith(("f", "F", "d", "D")) and not v.lower().endswith("infinity"):
        v = v[:-1]
    negative = v.startswith("-")
    body = v[1:] if negative else v
    try:
        body = format(Decimal(body), "f")
    except (InvalidOperation, ValueError):
        return v
    if body.startswith("-"):  # Decimal("-0") style input after sign removal cannot happen, be safe
        body = body[1:]
    return f"-{body}" if negative else body


def floating_constraint(value: str, is_float: bool) -> str:
    box = "Float" if is_float else "Double"
    v = value.strip()
    if v == "NaN":
        return f"{box}.isNaN({RESULT})"
    if v == "Infinity":
        return f"{RESULT} == {box}.POSITIVE_INFINITY"
    if v == "-Infinity":
        return f"{RESULT} == {box}.NEGATIVE_INFINITY"
    literal = plain_decimal(v)
    if "." not in literal:
        literal += ".0"
    return f"{RESULT} == {literal}{'f' if is_float else ''}"


def value_from_bits(bits: str, type_name: Optional[str]) -> Optional[str]:
    """The Java ``toString`` form of a float/double given its IEEE bits (``0x3dcccccd``)."""
    t = normalize_type(type_name)
    if t not in ("float", "double"):
        return None
    try:
        n = int(str(bits).strip(), 0)
    except ValueError:
        return None
    try:
        if t == "float":
            f = struct.unpack(">f", struct.pack(">I", n & 0xFFFFFFFF))[0]
        else:
            f = struct.unpack(">d", struct.pack(">Q", n & 0xFFFFFFFFFFFFFFFF))[0]
    except struct.error:
        return None
    if f != f:
        return "NaN"
    if f in (float("inf"), float("-inf")):
        return "Infinity" if f > 0 else "-Infinity"
    if f == 0.0:
        return "-0.0" if str(f).startswith("-") else "0.0"
    return repr(f)


def graphml_assumption_value(value: str, type_name: Optional[str]) -> str:
    """The right-hand side of a GraphML assumption, as wit4java's harness parses it.

    Primitives are plain decimal values that ``Integer.parseInt``/``Float.parseFloat``
    accept (chars as their code point, no ``L``/``f`` suffixes); strings become
    ``.equals("<java literal>")``.
    """
    value = "" if value is None else str(value)
    t = normalize_type(type_name)
    if t is None:
        v = value.strip()
        if _INT_RE.match(v) or v in ("true", "false"):
            return v
        return f".equals({string_literal(value)})"
    if t == "String":
        return f".equals({string_literal(value)})"
    if t == "boolean":
        return "true" if value.strip() == "true" else "false"
    if t == "char":
        v = value.strip()
        if _INT_RE.match(v):
            return v
        if len(v) == 1:
            return str(ord(v))
        return v
    if t in ("float", "double"):
        v = value.strip()
        if v in ("NaN", "Infinity", "-Infinity"):
            return v
        return plain_decimal(v)
    return value.strip()
