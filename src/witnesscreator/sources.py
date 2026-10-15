"""The Java source files of a verification task and the lookup of classes in them."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Union

from .columns import mask_non_code

log = logging.getLogger("witnesscreator")

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_PACKAGE_DECL = re.compile(r"^\s*package\s+([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)\s*;", re.MULTILINE)
_UNSET = object()


def to_slashes(s: str) -> str:
    return str(s).replace("\\", "/")


def strip_trailing_slash(s: str) -> str:
    r = to_slashes(s)
    while len(r) > 1 and r.endswith("/"):
        r = r[:-1]
    return r


def split_lines(text: str) -> List[str]:
    """Splits on ``\\n``, ``\\r\\n`` and ``\\r`` only (like ``Files.readAllLines``)."""
    if text == "":
        return []
    lines = _LINE_BREAK.split(text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


class InputFile:
    """One ``.java`` file of the task."""

    def __init__(self, display_path: str, path: Path, relative_path: str):
        #: The path as written into the witness: the input as given plus the relative path.
        self.display_path = display_path
        #: Where the file is read from.
        self.path = path
        #: Path relative to the input root it was found in, ``/``-separated.
        self.relative_path = relative_path
        self._lines: Optional[List[str]] = None
        self._masked: Optional[List[str]] = None
        self._sha256: Optional[str] = None
        self._package = _UNSET

    @property
    def file_name(self) -> str:
        return self.path.name

    def _read(self) -> str:
        try:
            return self.path.read_bytes().decode("utf-8", errors="replace")
        except OSError as e:
            log.warning("Could not read %s: %s", self.path, e)
            return ""

    @property
    def lines(self) -> List[str]:
        if self._lines is None:
            self._lines = split_lines(self._read())
        return self._lines

    @property
    def masked_lines(self) -> List[str]:
        """The lines with comments and string/char literals blanked out."""
        if self._masked is None:
            self._masked = split_lines(mask_non_code("\n".join(self.lines) + "\n"))
            while len(self._masked) < len(self.lines):
                self._masked.append("")
        return self._masked

    @property
    def package(self) -> Optional[str]:
        """The declared package (``""`` for the default package), ``None`` if unreadable."""
        if self._package is _UNSET:
            if not self.lines:
                self._package = None
            else:
                m = _PACKAGE_DECL.search("\n".join(self.masked_lines))
                self._package = m.group(1) if m else ""
        return self._package

    def line(self, number: int) -> Optional[str]:
        """The 1-based line, or ``None`` if the file does not have it."""
        if number < 1 or number > len(self.lines):
            return None
        return self.lines[number - 1]

    def masked_line(self, number: int) -> Optional[str]:
        if number < 1 or number > len(self.lines):
            return None
        return self.masked_lines[number - 1]

    @property
    def sha256(self) -> str:
        if self._sha256 is None:
            try:
                self._sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
            except OSError as e:
                log.warning("Could not hash %s: %s", self.path, e)
                self._sha256 = ""
        return self._sha256

    def __repr__(self) -> str:
        return f"InputFile({self.display_path!r})"


class SourceFiles:
    """The ``.java`` files of the task, in the order of the inputs."""

    def __init__(self, files: List[InputFile]):
        self.files = list(files)

    def __len__(self) -> int:
        return len(self.files)

    def __iter__(self):
        return iter(self.files)

    @classmethod
    def collect(cls, inputs: Iterable[str], base_dir: Union[str, Path, None] = None) -> "SourceFiles":
        """Collects the ``.java`` files of the inputs (files or directories, searched recursively).

        A file reachable through several inputs is listed once. Relative inputs are
        resolved against ``base_dir`` but displayed as given.
        """
        base = Path(base_dir) if base_dir is not None else None
        files: List[InputFile] = []
        seen = set()
        for given in inputs:
            given = str(given)
            if given == "":
                continue
            root = Path(given)
            if base is not None and not root.is_absolute():
                root = base / root
            try:
                if root.is_dir():
                    prefix = strip_trailing_slash(given)
                    found = []
                    for dirpath, dirnames, filenames in os.walk(root):
                        dirnames.sort()
                        for name in filenames:
                            if name.endswith(".java"):
                                found.append(Path(dirpath) / name)
                    found.sort(key=lambda p: to_slashes(str(p)))
                    for p in found:
                        key = os.path.normpath(os.path.abspath(p))
                        if key in seen:
                            continue
                        seen.add(key)
                        rel = to_slashes(str(p.relative_to(root)))
                        files.append(InputFile(f"{prefix}/{rel}", p, rel))
                elif root.is_file():
                    if not root.name.endswith(".java"):
                        log.info("Ignoring input that is not a Java source: %s", given)
                        continue
                    key = os.path.normpath(os.path.abspath(root))
                    if key in seen:
                        continue
                    seen.add(key)
                    files.append(InputFile(to_slashes(given), root, root.name))
                else:
                    log.warning("Ignoring missing input: %s", given)
            except OSError as e:
                log.warning("Could not read input %s: %s", given, e)
        return cls(files)

    def _find(self, predicate: Callable[[InputFile], bool]) -> Optional[InputFile]:
        for f in self.files:
            if predicate(f):
                return f
        return None

    def resolve(
        self, class_name: str, source_file_name: Optional[str], allow_name_only: bool = True
    ) -> Optional[InputFile]:
        """Finds the source file of a class.

        ``class_name`` may be JVM internal (``pkg/Outer$Inner``) or dotted
        (``pkg.Outer$Inner``); ``source_file_name`` is the class' ``SourceFile``
        attribute, if known.

        Candidates are the files of the expected name; a candidate whose ``package``
        declaration contradicts the class' package is never taken. Among the rest,
        the file whose path inside its input matches the package path wins (exact
        match first, then as a suffix). A file whose package declaration matches is
        accepted regardless of its path; a file whose declaration could not be read
        only with ``allow_name_only``.
        """
        internal = str(class_name).replace(".", "/")
        slash = internal.rfind("/")
        pkg_dir = "" if slash < 0 else internal[:slash]
        package = pkg_dir.replace("/", ".")
        simple = internal if slash < 0 else internal[slash + 1 :]
        dollar = simple.find("$")
        outer = simple if dollar < 0 else simple[:dollar]

        names: List[str] = []
        if source_file_name:
            names.append(to_slashes(source_file_name).rsplit("/", 1)[-1])
        if f"{outer}.java" not in names:
            names.append(f"{outer}.java")

        for name in names:
            candidates = [f for f in self.files if f.file_name == name and f.package in (package, None)]
            if not candidates:
                continue
            rel = name if not pkg_dir else f"{pkg_dir}/{name}"
            for f in candidates:
                if f.relative_path == rel:
                    return f
            for f in candidates:
                if f.relative_path.endswith("/" + rel):
                    return f
            for f in candidates:
                if f.package == package:
                    return f
            if allow_name_only:
                return candidates[0]
        return None

    def resolve_file_name(self, file_name: str) -> Optional[InputFile]:
        """Finds an input file by the path a producer wrote (as given, relative, or by name)."""
        name = to_slashes(file_name)
        while name.startswith("./"):
            name = name[2:]
        if not name:
            return None
        for pred in (
            lambda f: f.display_path == name,
            lambda f: f.relative_path == name,
            lambda f: f.display_path.endswith("/" + name),
            lambda f: f.relative_path.endswith("/" + name),
            lambda f: f.file_name == name.rsplit("/", 1)[-1],
        ):
            match = self._find(pred)
            if match is not None:
                return match
        return None


def fallback_file_name(class_name: str, source_file: Optional[str]) -> str:
    """The file a class should live in when it was not found among the inputs."""
    internal = str(class_name).replace(".", "/")
    slash = internal.rfind("/")
    pkg_dir = "" if slash < 0 else internal[: slash + 1]
    if source_file:
        return pkg_dir + to_slashes(source_file).rsplit("/", 1)[-1]
    simple = internal[slash + 1 :]
    dollar = simple.find("$")
    return pkg_dir + (simple if dollar < 0 else simple[:dollar]) + ".java"
