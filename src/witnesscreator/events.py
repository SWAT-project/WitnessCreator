"""The event file: JSON lines carrying the model objects.

::

    {"kind": "header", "schema": "witnesscreator-events", "version": 1, "producer": {"name": "SWAT", "version": "svcomp27"}}
    {"kind": "nondet_return", "function": "nondetInt", "type": "int", "value": "42", "location": {...}, "bits": null}
    {"kind": "violation", "throwable": "java.lang.AssertionError", "frames": [{"class_name": "Main", "source_file": "Main.java", "line": 17}]}

The ``producer`` of the header is optional. Unknown lines are skipped with a
warning; a later ``violation`` line replaces an earlier one.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .model import Frame, Location, NondetReturn, Violation

log = logging.getLogger("witnesscreator")

SCHEMA = "witnesscreator-events"
VERSION = 1


def header_dict(producer_name: Optional[str] = None, producer_version: Optional[str] = None) -> Dict[str, Any]:
    header: Dict[str, Any] = {"kind": "header", "schema": SCHEMA, "version": VERSION}
    if producer_name is not None or producer_version is not None:
        header["producer"] = {"name": producer_name, "version": producer_version}
    return header


def nondet_return_to_dict(nr: NondetReturn) -> Dict[str, Any]:
    d: Dict[str, Any] = {"kind": "nondet_return"}
    d.update(asdict(nr))
    return d


def violation_to_dict(v: Violation) -> Dict[str, Any]:
    d: Dict[str, Any] = {"kind": "violation"}
    d.update(asdict(v))
    return d


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _opt_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def location_from_dict(d: Any) -> Location:
    if not isinstance(d, dict):
        return Location()
    column = d.get("column")
    return Location(
        class_name=_opt_str(d.get("class_name")),
        source_file=_opt_str(d.get("source_file")),
        line=_int(d.get("line"), 0),
        call_index=_int(d.get("call_index"), 0),
        file_name=_opt_str(d.get("file_name")),
        column=None if column is None else _int(column, 0) or None,
        method=_opt_str(d.get("method")),
    )


def nondet_return_from_dict(d: Dict[str, Any]) -> NondetReturn:
    value = d.get("value")
    return NondetReturn(
        function=_opt_str(d.get("function")),
        type=_opt_str(d.get("type")),
        value="" if value is None else (value if isinstance(value, str) else json.dumps(value)),
        location=location_from_dict(d.get("location")),
        bits=_opt_str(d.get("bits")),
    )


def frame_from_dict(d: Any) -> Optional[Frame]:
    if not isinstance(d, dict):
        return None
    return Frame(str(d.get("class_name") or ""), _opt_str(d.get("source_file")), _int(d.get("line"), -1))


def violation_from_dict(d: Dict[str, Any]) -> Violation:
    frames = [f for f in (frame_from_dict(x) for x in (d.get("frames") or [])) if f is not None]
    return Violation(str(d.get("throwable") or "unknown"), frames)


@dataclass
class EventFile:
    header: Dict[str, Any] = field(default_factory=dict)
    values: List[NondetReturn] = field(default_factory=list)
    violation: Optional[Violation] = None

    @property
    def producer_name(self) -> Optional[str]:
        p = self.header.get("producer")
        return _opt_str(p.get("name")) if isinstance(p, dict) else None

    @property
    def producer_version(self) -> Optional[str]:
        p = self.header.get("producer")
        return _opt_str(p.get("version")) if isinstance(p, dict) else None


def parse_events(lines: Iterable[str]) -> EventFile:
    """Parses event lines leniently: bad lines are logged and skipped."""
    ev = EventFile()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError as e:
            log.warning("Skipping event line %d (%s): %s", number, e, line[:120])
            continue
        if not isinstance(d, dict):
            log.warning("Skipping event line %d: not an object", number)
            continue
        kind = d.get("kind")
        try:
            if kind == "header":
                if d.get("schema") != SCHEMA:
                    log.warning("Unexpected event schema %r (expected %r)", d.get("schema"), SCHEMA)
                if _int(d.get("version"), VERSION) > VERSION:
                    log.warning("Event file version %s is newer than %s", d.get("version"), VERSION)
                ev.header = d
            elif kind == "nondet_return":
                ev.values.append(nondet_return_from_dict(d))
            elif kind == "violation":
                if ev.violation is not None:
                    log.info("Event line %d replaces an earlier violation", number)
                ev.violation = violation_from_dict(d)
            else:
                log.warning("Skipping event line %d of unknown kind %r", number, kind)
        except Exception as e:  # noqa: BLE001
            log.warning("Skipping event line %d (%s)", number, e)
    return ev


def read_events(path: Union[str, Path]) -> EventFile:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return parse_events(fh)


def dump_events(
    values: Iterable[NondetReturn],
    violation: Optional[Violation],
    producer_name: Optional[str] = None,
    producer_version: Optional[str] = None,
) -> str:
    """The event file text for the given objects (header first)."""
    out = [json.dumps(header_dict(producer_name, producer_version))]
    for nr in values:
        out.append(json.dumps(nondet_return_to_dict(nr)))
    if violation is not None:
        out.append(json.dumps(violation_to_dict(violation)))
    return "\n".join(out) + "\n"
