"""Hand-written emitter for violation witnesses in the YAML format, version 2.3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

FORMAT_VERSION = "2.3"

_YAML_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\x85": "\\N",
    " ": "\\L",
    " ": "\\P",
}


def yaml_quote(s: str) -> str:
    """Renders a YAML double-quoted scalar.

    Everything outside printable ASCII is escaped (``\\uXXXX``, ``\\UXXXXXXXX`` for
    characters beyond the BMP), so the output is plain ASCII that every YAML parser
    decodes to the same string, including control characters and lone surrogates.
    """
    out = ['"']
    for ch in str(s):
        esc = _YAML_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
            continue
        c = ord(ch)
        if 0x20 <= c < 0x7F:
            out.append(ch)
        elif c > 0xFFFF:
            out.append(f"\\U{c:08x}")
        else:
            out.append(f"\\u{c:04x}")
    out.append('"')
    return "".join(out)


@dataclass
class Waypoint:
    """A ``follow`` waypoint of the single violation sequence."""

    type: str
    constraint: Optional[str]
    file_name: str
    line: int
    column: Optional[int] = None

    @classmethod
    def function_return(cls, constraint: str, file_name: str, line: int, column: Optional[int]):
        return cls("function_return", constraint, file_name, line, column)

    @classmethod
    def target(cls, file_name: str, line: int, column: Optional[int]):
        return cls("target", None, file_name, line, column)

    def __str__(self) -> str:
        s = f"{self.type} @ {self.file_name}:{self.line}"
        if self.column is not None:
            s += f":{self.column}"
        if self.constraint is not None:
            s += f" [{self.constraint}]"
        return s


@dataclass
class Metadata:
    uuid: str
    creation_time: str
    producer_name: str
    producer_version: str
    specification: str
    input_files: Sequence[Tuple[str, str]]  # (display path, sha256)


def render_yaml(metadata: Metadata, waypoints: List[Waypoint]) -> str:
    """The witness document: one ``violation_sequence`` entry, one segment per waypoint."""
    q = yaml_quote
    out = []
    out.append('- entry_type: "violation_sequence"\n')
    out.append("  metadata:\n")
    out.append(f"    format_version: {q(FORMAT_VERSION)}\n")
    out.append(f"    uuid: {q(metadata.uuid)}\n")
    out.append(f"    creation_time: {q(metadata.creation_time)}\n")
    out.append("    producer:\n")
    out.append(f"      name: {q(metadata.producer_name)}\n")
    out.append(f"      version: {q(metadata.producer_version)}\n")
    out.append("    task:\n")
    if not metadata.input_files:
        out.append("      input_files: []\n")
        out.append("      input_file_hashes: {}\n")
    else:
        out.append("      input_files:\n")
        for path, _ in metadata.input_files:
            out.append(f"      - {q(path)}\n")
        out.append("      input_file_hashes:\n")
        for path, sha in metadata.input_files:
            out.append(f"        {q(path)}: {q(sha)}\n")
    out.append(f"      specification: {q(metadata.specification)}\n")
    out.append('      language: "Java"\n')
    if not waypoints:
        out.append("  content: []\n")
        return "".join(out)
    out.append("  content:\n")
    for wp in waypoints:
        out.append("  - segment:\n")
        out.append("    - waypoint:\n")
        out.append(f"        type: {q(wp.type)}\n")
        out.append('        action: "follow"\n')
        if wp.constraint is not None:
            out.append("        constraint:\n")
            out.append(f"          value: {q(wp.constraint)}\n")
            out.append('          format: "java_expression"\n')
        out.append("        location:\n")
        out.append(f"          file_name: {q(wp.file_name)}\n")
        out.append(f"          line: {int(wp.line)}\n")
        if wp.column is not None:
            out.append(f"          column: {int(wp.column)}\n")
    return "".join(out)
