"""Command line interface.

::

    witnesscreator events --events E.jsonl --property P.prp --input PATH... --out-dir D
                          [--format yaml|graphml|both] [--producer-name N] [--producer-version V]
    witnesscreator legacy [<base64 markers> [<dir>]] [--markers-file F] --input PATH... --property P.prp
                          --out-dir D [--format ...] [--producer-name N] [--producer-version V]
    witnesscreator <base64 markers> [<dir>] [--input PATH]... [--property P.prp] [--out D]
                          [--producer-version V]           (the Java WitnessCreator's command line)

Exit status 0 once a witness was written, 1 if nothing could be written, 2 for usage errors.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from ._version import __version__
from .events import read_events
from .markers import parse_markers
from .model import Task
from .witness import FORMATS, write_witnesses

log = logging.getLogger("witnesscreator")

SUBCOMMANDS = ("events", "legacy")
LEGACY_PRODUCER = "SWAT"


def _formats(choice: str) -> Sequence[str]:
    return FORMATS if choice == "both" else (choice,)


def _add_common(p: argparse.ArgumentParser, producer_name: Optional[str], producer_version: Optional[str]) -> None:
    p.add_argument("--input", action="append", default=[], metavar="PATH",
                   help="input file or directory of the task, exactly as given to the verifier (repeatable)")
    p.add_argument("--property", metavar="FILE.prp", help="the property file; its content becomes the specification")
    p.add_argument("--out-dir", "--out", dest="out_dir", metavar="DIR", help="where witness.yml / witness.graphml are written")
    p.add_argument("--format", choices=("yaml", "graphml", "both"), default="both", help="which witness formats to write (default: both)")
    p.add_argument("--producer-name", default=producer_name, metavar="NAME",
                   help=f"metadata.producer.name (default: {producer_name or 'the event file header, else witnesscreator'})")
    p.add_argument("--producer-version", default=producer_version, metavar="VERSION",
                   help=f"metadata.producer.version (default: {producer_version or 'the event file header, else the witnesscreator version'})")
    p.add_argument("--base-dir", metavar="DIR", help="resolve relative input and property paths against this directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="witnesscreator",
        description="Creates SV-COMP violation witnesses for Java (YAML format 2.3 and legacy GraphML).",
    )
    parser.add_argument("--version", action="version", version=f"witnesscreator {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug output")
    parser.add_argument("-q", "--quiet", action="store_true", help="only warnings and errors")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    events = sub.add_parser("events", help="create witnesses from an event file (JSON lines)")
    events.add_argument("--events", required=True, metavar="FILE.jsonl", help="the event file")
    _add_common(events, None, None)

    legacy = sub.add_parser(
        "legacy",
        help="create witnesses from SWAT's [WITNESS] / [WITNESS_TARGET] marker lines",
        description="The markers are given base64-encoded on the command line (as SWAT printed them) "
                    "or as a file of marker lines. The positional <dir> is both an input and the default "
                    "output directory, like the Java WitnessCreator's.",
    )
    legacy.add_argument("markers", nargs="?", default=None, metavar="BASE64",
                        help="base64 of the output lines carrying the markers (empty for the default violation witness)")
    legacy.add_argument("dir", nargs="?", default=None, metavar="DIR", help="legacy: the task directory, also the output directory")
    legacy.add_argument("--markers-file", metavar="FILE", help="file with the marker lines (plain text or base64)")
    _add_common(legacy, LEGACY_PRODUCER, "unknown")
    return parser


def _configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger = logging.getLogger("witnesscreator")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False


def _normalize_argv(argv: List[str]) -> List[str]:
    """The Java command line (``<markers> [<dir>] [--input ...]``) becomes ``legacy ...``."""
    if not argv:
        return argv
    first = argv[0]
    if first in SUBCOMMANDS or first in ("-h", "--help", "--version"):
        return argv
    if first in ("-v", "--verbose", "-q", "--quiet") and len(argv) > 1 and argv[1] in SUBCOMMANDS:
        return argv
    return ["legacy"] + argv


def run_events(args: argparse.Namespace) -> int:
    try:
        ev = read_events(args.events)
    except OSError as e:
        log.error("Could not read event file %s: %s", args.events, e)
        ev = None
    values = ev.values if ev else []
    violation = ev.violation if ev else None
    task = Task(
        input_files=list(args.input),
        property_file=args.property,
        producer_name=args.producer_name or (ev.producer_name if ev else None) or "witnesscreator",
        producer_version=args.producer_version or (ev.producer_version if ev else None) or __version__,
        base_dir=args.base_dir,
    )
    written = write_witnesses(task, values, violation, args.out_dir or ".", _formats(args.format))
    return 0 if written else 1


def run_legacy(args: argparse.Namespace) -> int:
    text = ""
    if args.markers_file:
        try:
            text = Path(args.markers_file).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            log.error("Could not read markers file %s: %s", args.markers_file, e)
    if args.markers:
        text = (text + "\n" + args.markers) if text.strip() else args.markers
    values, violation = parse_markers(text)

    inputs = list(args.input)
    if not inputs and args.dir:
        inputs.append(args.dir)
    out_dir = args.out_dir or args.dir or "."
    task = Task(
        input_files=inputs,
        property_file=args.property,
        producer_name=args.producer_name or LEGACY_PRODUCER,
        producer_version=args.producer_version or "unknown",
        base_dir=args.base_dir,
    )
    log.info("inputs: %s", inputs)
    log.info("output directory: %s", out_dir)
    written = write_witnesses(task, values, violation, out_dir, _formats(args.format))
    return 0 if written else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(_normalize_argv(argv))
    _configure_logging(args.verbose, args.quiet)
    if args.command == "events":
        return run_events(args)
    if args.command == "legacy":
        return run_legacy(args)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
