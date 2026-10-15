"""Turns a task, the recorded values and the violation into witness documents."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .columns import nondet_call_column, statement_column
from .graphml_writer import Assumption, render_graphml as _render_graphml
from .literals import graphml_assumption_value, result_constraint, value_from_bits
from .model import Location, NondetReturn, Task, Violation
from .sources import InputFile, SourceFiles, fallback_file_name, to_slashes
from .yaml_writer import Metadata, Waypoint, render_yaml as _render_yaml

log = logging.getLogger("witnesscreator")

DEFAULT_SPECIFICATION = "CHECK( init(Main.main()), LTL(G assert) )"
FORMATS = ("yaml", "graphml")
FILE_NAMES = {"yaml": "witness.yml", "graphml": "witness.graphml"}

#: Stack frames of these packages never are the target: the violating statement is
#: the innermost frame of the task sources that called into them.
SKIPPED_FRAME_PREFIXES = ("java.", "javax.", "jdk.", "sun.", "de.uzl.its.swat.")


@dataclass
class BuiltWitness:
    """Everything the writers need, computed once for all formats."""

    metadata: Metadata
    waypoints: List[Waypoint] = field(default_factory=list)
    assumptions: List[Assumption] = field(default_factory=list)
    target: Optional[Waypoint] = None

    @property
    def has_target(self) -> bool:
        return self.target is not None


def read_specification(property_file: Union[str, Path, None], base_dir: Union[str, Path, None] = None) -> str:
    """The content of the property file; the default specification if it cannot be read."""
    if property_file is None or str(property_file) == "":
        log.warning("No property file given, assuming specification: %s", DEFAULT_SPECIFICATION)
        return DEFAULT_SPECIFICATION
    path = Path(property_file)
    if base_dir is not None and not path.is_absolute():
        path = Path(base_dir) / path
    try:
        spec = path.read_bytes().decode("utf-8", errors="replace").strip()
    except OSError as e:
        log.warning("Could not read property file %s: %s", property_file, e)
        spec = ""
    if spec:
        return spec
    log.warning("Assuming specification: %s", DEFAULT_SPECIFICATION)
    return DEFAULT_SPECIFICATION


def _scope(class_name: Optional[str], method: Optional[str], file_name: Optional[str]) -> str:
    if class_name:
        internal = str(class_name).replace(".", "/")
    elif file_name:
        internal = to_slashes(file_name).rsplit("/", 1)[-1]
        if internal.endswith(".java"):
            internal = internal[: -len(".java")]
    else:
        internal = ""
    scope = f"java::L{internal};"
    if method:
        scope += f".{method}"
    return scope


class _Builder:
    def __init__(self, task: Task, sources: SourceFiles):
        self.task = task
        self.sources = sources

    def value(self, nr: NondetReturn) -> Tuple[Optional[Waypoint], Optional[Assumption]]:
        loc = nr.location if nr.location is not None else Location()
        value = nr.value
        if (value is None or value == "") and nr.bits:
            derived = value_from_bits(nr.bits, nr.type)
            if derived is not None:
                value = derived
        value = "" if value is None else str(value)
        try:
            line = int(loc.line)
        except (TypeError, ValueError):
            line = 0
        if line < 1:
            log.warning("Ignoring value %r without a valid line: %s", value, loc)
            return None, None

        found: Optional[InputFile] = None
        if loc.file_name:
            found = self.sources.resolve_file_name(loc.file_name)
            display = found.display_path if found else to_slashes(loc.file_name)
            origin = found.relative_path if found else to_slashes(loc.file_name)
            if found is None:
                log.warning("%s is not among the input files, using it as given", loc.file_name)
        elif loc.class_name:
            found = self.sources.resolve(loc.class_name, loc.source_file, allow_name_only=True)
            if found is not None:
                display = found.display_path
                origin = found.relative_path
            else:
                display = origin = fallback_file_name(loc.class_name, loc.source_file)
                log.warning("Could not find the source of %s, using %s", loc.class_name, display)
        else:
            log.warning("Ignoring value %r without a file or class: %s", value, loc)
            return None, None

        column = loc.column
        if column is not None:
            try:
                column = int(column)
            except (TypeError, ValueError):
                column = None
            if column is not None and column < 1:
                column = None
        if column is None and found is not None:
            code = found.masked_line(line)
            column = nondet_call_column(code, loc.call_index) if code is not None else None
            if column is None:
                log.warning(
                    "Could not locate nondet call %s in %s:%s (%r)",
                    loc.call_index, display, line, found.line(line),
                )

        constraint = result_constraint(value, nr.type)
        waypoint = Waypoint.function_return(constraint, display, line, column)
        scope = _scope(loc.class_name, loc.method, display)
        rhs = graphml_assumption_value(value, nr.type)
        text = f"\\result{rhs};" if rhs.startswith(".equals(") else f"\\result = {rhs};"
        return waypoint, Assumption(origin, line, text, scope)

    def target(self, violation: Violation) -> Optional[Waypoint]:
        for frame in violation.frames or []:
            try:
                line = int(frame.line)
            except (TypeError, ValueError):
                continue
            if line < 1:
                continue
            class_name = str(frame.class_name or "").replace("/", ".")
            if not class_name or class_name.startswith(SKIPPED_FRAME_PREFIXES):
                continue
            found = self.sources.resolve(class_name, frame.source_file, allow_name_only=False)
            if found is None:
                continue
            code = found.masked_line(line)
            if code is None:
                log.warning("Frame %s:%s is outside of %s", class_name, line, found.path)
                continue
            column = statement_column(code, violation.is_assertion_error)
            return Waypoint.target(found.display_path, line, column)
        return None


def build_witness(task: Task, values: Iterable[NondetReturn], violation: Optional[Violation]) -> BuiltWitness:
    """Resolves locations and renders constraints; never raises for bad values."""
    sources = SourceFiles.collect(task.input_files or [], task.base_dir)
    specification = read_specification(task.property_file, task.base_dir)
    metadata = Metadata(
        uuid=str(uuid.uuid4()),
        creation_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        producer_name=str(task.producer_name),
        producer_version=str(task.producer_version),
        specification=specification,
        input_files=[(f.display_path, f.sha256) for f in sources],
    )
    built = BuiltWitness(metadata)
    builder = _Builder(task, sources)

    for nr in values or []:
        try:
            waypoint, assumption = builder.value(nr)
        except Exception as e:  # noqa: BLE001 - a bad value must not lose the witness
            log.error("Ignoring value %r: %s", nr, e)
            continue
        if waypoint is not None:
            built.waypoints.append(waypoint)
        if assumption is not None:
            built.assumptions.append(assumption)
    if not built.waypoints:
        log.info("No witness values recorded, assuming default violation")

    if violation is not None:
        try:
            built.target = builder.target(violation)
        except Exception as e:  # noqa: BLE001
            log.error("Could not resolve the target of %r: %s", violation, e)
        if built.target is None:
            log.warning(
                "No stack frame of %s lies in the task sources, the witness has no target waypoint: %s",
                violation.throwable, violation.frames,
            )
        else:
            built.waypoints.append(built.target)
    else:
        log.warning("No violation recorded, the witness has no target waypoint")

    for wp in built.waypoints:
        log.info("Waypoint: %s", wp)
    return built


def render_yaml(task: Task, values: Iterable[NondetReturn], violation: Optional[Violation]) -> str:
    """The YAML (format 2.3) witness as a string."""
    built = build_witness(task, values, violation)
    return _render_yaml(built.metadata, built.waypoints)


def render_graphml(task: Task, values: Iterable[NondetReturn], violation: Optional[Violation]) -> str:
    """The legacy GraphML witness as a string."""
    built = build_witness(task, values, violation)
    return _render_graphml(built.metadata.producer_name, built.metadata.specification, built.assumptions)


def _render(built: BuiltWitness, fmt: str) -> str:
    if fmt == "yaml":
        return _render_yaml(built.metadata, built.waypoints)
    if fmt == "graphml":
        return _render_graphml(built.metadata.producer_name, built.metadata.specification, built.assumptions)
    raise ValueError(f"unknown witness format: {fmt}")


def write_witnesses(
    task: Task,
    values: Iterable[NondetReturn],
    violation: Optional[Violation],
    out_dir: Union[str, Path] = "output",
    formats: Sequence[str] = FORMATS,
) -> Dict[str, Path]:
    """Writes ``witness.yml`` and/or ``witness.graphml`` into ``out_dir``.

    Never raises for bad data: problems are logged (logger ``witnesscreator``) and
    each format is written independently. Returns the files actually written, by
    format.
    """
    written: Dict[str, Path] = {}
    wanted = [f for f in (formats or ()) if f in FORMATS]
    for f in formats or ():
        if f not in FORMATS:
            log.error("Unknown witness format %r (known: %s)", f, ", ".join(FORMATS))
    if not wanted:
        return written

    values = list(values or [])
    try:
        built = build_witness(task, values, violation)
    except Exception as e:  # noqa: BLE001 - last line of defence
        log.error("Could not build the witness, writing a witness without waypoints: %s", e)
        metadata = Metadata(
            uuid=str(uuid.uuid4()),
            creation_time=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            producer_name=str(getattr(task, "producer_name", "unknown")),
            producer_version=str(getattr(task, "producer_version", "unknown")),
            specification=DEFAULT_SPECIFICATION,
            input_files=[],
        )
        built = BuiltWitness(metadata)

    out = Path(out_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.error("Could not create output directory %s: %s", out, e)
    for fmt in wanted:
        path = out / FILE_NAMES[fmt]
        try:
            text = _render(built, fmt)
            log.info("Writing violation witness to file: %s", path)
            path.write_text(text, encoding="utf-8", newline="\n")
            written[fmt] = path
        except Exception as e:  # noqa: BLE001
            log.error("Could not write %s witness to %s: %s", fmt, path, e)
    return written
