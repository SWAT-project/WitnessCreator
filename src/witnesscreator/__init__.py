"""witnesscreator: SV-COMP violation witnesses for Java.

>>> from witnesscreator import Task, Location, NondetReturn, Frame, Violation, write_witnesses
>>> task = Task(input_files=["../common/", "Main.java"], property_file="valid-assert.prp",
...             producer_name="MyVerifier", producer_version="1.0")
>>> values = [NondetReturn("nondetInt", "int", "42",
...                        Location(class_name="Main", source_file="Main.java", line=12, call_index=0))]
>>> violation = Violation("java.lang.AssertionError", [Frame("Main", "Main.java", 17)])
>>> write_witnesses(task, values, violation, out_dir="output")  # doctest: +SKIP
{'yaml': PosixPath('output/witness.yml'), 'graphml': PosixPath('output/witness.graphml')}
"""

from ._version import __version__
from .events import dump_events, parse_events, read_events
from .markers import parse_marker_lines, parse_markers
from .model import JAVA_TYPES, Frame, Location, NondetReturn, Task, Violation
from .witness import FORMATS, render_graphml, render_yaml, write_witnesses

__all__ = [
    "__version__",
    "JAVA_TYPES",
    "FORMATS",
    "Task",
    "Location",
    "NondetReturn",
    "Frame",
    "Violation",
    "write_witnesses",
    "render_yaml",
    "render_graphml",
    "parse_markers",
    "parse_marker_lines",
    "read_events",
    "parse_events",
    "dump_events",
]
