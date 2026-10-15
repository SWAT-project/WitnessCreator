"""The data model shared by the library, the event file and the command line.

Every object is a plain dataclass; ``write_witnesses`` never mutates them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence, Union

from ._version import __version__

#: Java types of ``Verifier.nondet*()`` results, as spelled in :attr:`NondetReturn.type`.
JAVA_TYPES = ("boolean", "byte", "short", "char", "int", "long", "float", "double", "String")

_DESCRIPTOR_TO_TYPE = {
    "Z": "boolean",
    "B": "byte",
    "S": "short",
    "C": "char",
    "I": "int",
    "J": "long",
    "F": "float",
    "D": "double",
    "Ljava/lang/String;": "String",
    "java.lang.String": "String",
    "java/lang/String": "String",
    "string": "String",
}


def normalize_type(type_name: Optional[str]) -> Optional[str]:
    """Maps a Java type name or JVM descriptor to one of :data:`JAVA_TYPES`.

    Returns ``None`` for an unknown or missing type, which selects the legacy
    rendering that only looks at the value.
    """
    if type_name is None:
        return None
    t = str(type_name).strip()
    if t in JAVA_TYPES:
        return t
    return _DESCRIPTOR_TO_TYPE.get(t)


@dataclass
class Location:
    """Where a ``Verifier.nondet*()`` call happened.

    Two forms are accepted:

    * ``Location(class_name="pkg.Main", source_file="Main.java", line=12, call_index=0)``:
      the call site is resolved to one of the task's source files and the column is
      derived from the source text;
    * ``Location(file_name="Main.java", line=12, column=27)``: the producer already
      knows the file (one of the task's input files) and, optionally, the column.

    ``method`` optionally names the calling method (``main([Ljava/lang/String;)V``);
    it only appears in the GraphML ``assumption.scope``.
    """

    class_name: Optional[str] = None
    source_file: Optional[str] = None
    line: int = 0
    call_index: int = 0
    file_name: Optional[str] = None
    column: Optional[int] = None
    method: Optional[str] = None


@dataclass
class NondetReturn:
    """One value returned by a ``Verifier.nondet*()`` call.

    ``value`` is the string form of the value: integers in decimal, ``char`` as its
    code point in decimal, ``boolean`` as ``true``/``false``, ``float``/``double`` as
    Java's ``Float.toString``/``Double.toString`` (``NaN``, ``Infinity``,
    ``-Infinity``, ``-0.0`` included) and ``String`` as the raw, unescaped string.
    """

    function: Optional[str]
    type: Optional[str]
    value: str
    location: Location
    bits: Optional[str] = None


@dataclass
class Frame:
    """A stack frame of the uncaught throwable, as ``StackTraceElement`` reports it."""

    class_name: str
    source_file: Optional[str] = None
    line: int = -1


@dataclass
class Violation:
    """The uncaught throwable that ended the violating run, innermost frame first."""

    throwable: str
    frames: list = field(default_factory=list)

    @property
    def is_assertion_error(self) -> bool:
        return self.throwable == "java.lang.AssertionError"


@dataclass
class Task:
    """The verification task the witness belongs to.

    ``input_files`` are the files or directories exactly as given to the verifier;
    directories are expanded to the ``.java`` files they contain. ``property_file``
    is the ``.prp`` file whose content becomes the witness' specification.
    Relative input paths are resolved against ``base_dir`` (default: the current
    working directory) but written to the witness as given.
    """

    input_files: Sequence[str] = field(default_factory=list)
    property_file: Union[str, Path, None] = None
    producer_name: str = "witnesscreator"
    producer_version: str = __version__
    base_dir: Union[str, Path, None] = None
