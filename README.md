# WitnessCreator

WitnessCreator creates SV-COMP violation witnesses for Java programs:

- `witness.yml` in the [YAML witness format 2.3](https://gitlab.com/sosy-lab/benchmarking/sv-witnesses)
  (required for Java in SV-COMP 2027): one `violation_sequence` with a `function_return`
  waypoint per `Verifier.nondet*()` value (`\result == <java literal>` at the closing
  parenthesis of the call) and a final `target` waypoint at the violating statement;
- `witness.graphml` in the legacy GraphML format, for validators such as wit4java that
  still consume it.

It is a pure-Python package (Python >= 3.10, no runtime dependencies) with a library API,
a command line interface and a single-file `witnesscreator.pyz`. It is used by
[SWAT](https://github.com/SWAT-project/SWAT) but does not depend on it: any tool that knows
the values its `Verifier.nondet*()` calls returned and where the violation happened can use it.

## Installation

```sh
pip install git+https://github.com/SWAT-project/WitnessCreator@v1.0.0
```

or download `witnesscreator-<version>-py3-none-any.whl` / `witnesscreator.pyz` from the
[releases](https://github.com/SWAT-project/WitnessCreator/releases). The `.pyz` needs nothing
but a Python interpreter: `python3 witnesscreator.pyz ...`.

## Library

```python
from witnesscreator import Task, Location, NondetReturn, Frame, Violation, write_witnesses

task = Task(
    input_files=["../common/", "Main.java"],   # as given to the verifier; directories are expanded to *.java
    property_file="valid-assert.prp",          # its content becomes metadata.task.specification
    producer_name="MyVerifier", producer_version="1.0",
    base_dir=None,                             # resolve relative paths against this directory (default: cwd)
)

values = [
    NondetReturn(
        function="nondetInt",                  # Verifier method name
        type="int",                            # boolean|byte|short|char|int|long|float|double|String
        value="42",                            # decimal; char = code point; float/double as Java's toString
                                               # (NaN, Infinity, -Infinity, -0.0); String = the raw string
        location=Location(class_name="pkg.Main", source_file="Main.java", line=12, call_index=0),
        # or Location(file_name="Main.java", line=12, column=27) when file and column are already known
    ),
]

violation = Violation(
    throwable="java.lang.AssertionError",
    frames=[Frame(class_name="pkg.Main", source_file="Main.java", line=17)],  # innermost first
)  # or None if unknown

paths = write_witnesses(task, values, violation, out_dir="output", formats=("yaml", "graphml"))
# {'yaml': PosixPath('output/witness.yml'), 'graphml': PosixPath('output/witness.graphml')}
```

- `call_index` is the 0-based index of the call among the `nondet*` calls on that source
  line (left to right, which is Java's evaluation order). The column of the waypoint is the
  closing parenthesis of that call; calls inside comments and string literals are ignored.
- The target is the innermost stack frame that lies in the task sources (frames of `java.`,
  `javax.`, `jdk.`, `sun.` and `de.uzl.its.swat.` are skipped, the package of a class must match
  the file's path or `package` declaration). Its column is the `assert` of a failed assertion,
  the `throw` of an explicit throw, or the first token of the statement.
- `write_witnesses` never raises for bad data: problems are logged on the `witnesscreator`
  logger, each format is written independently and only the formats actually written are
  returned. Without a target a warning is logged and the witness has no `target` waypoint.
- `render_yaml(task, values, violation)` and `render_graphml(...)` return the documents as strings.

Values can also be exchanged through an event file (JSON lines, see below):
`dump_events(values, violation, producer_name, producer_version)` writes it,
`read_events(path)` reads it.

## Command line

`witnesscreator` (console script), `python -m witnesscreator` and `python3 witnesscreator.pyz`
are equivalent. Exit status is 0 once a witness was written, 1 if nothing could be written
and 2 for usage errors. Progress and warnings go to stderr.

### Event file

```sh
witnesscreator events --events run.jsonl --property valid-assert.prp \
    --input ../common/ --input Main.java --out-dir witness \
    [--format yaml|graphml|both] [--producer-name N] [--producer-version V] [--base-dir DIR]
```

`run.jsonl` holds one JSON object per line, the serialization of the objects above:

```json
{"kind": "header", "schema": "witnesscreator-events", "version": 1, "producer": {"name": "MyVerifier", "version": "1.0"}}
{"kind": "nondet_return", "function": "nondetInt", "type": "int", "value": "42", "location": {"class_name": "pkg.Main", "source_file": "Main.java", "line": 12, "call_index": 0}, "bits": null}
{"kind": "violation", "throwable": "java.lang.AssertionError", "frames": [{"class_name": "pkg.Main", "source_file": "Main.java", "line": 17}]}
```

The `producer` of the header is optional and overridden by `--producer-name` /
`--producer-version`. Unknown or malformed lines are skipped with a warning.

### Legacy markers (SWAT output lines)

```sh
witnesscreator legacy [<base64>] [--markers-file FILE] --input ../common/ --input Main.java \
    --property valid-assert.prp --out-dir witness [--format ...] [--producer-name N] [--producer-version V]
```

reads the `[WITNESS]` / `[WITNESS_TARGET]` markers SWAT printed, either as the base64 of the
output lines (as SWAT passed them to the Java tool) or from a file holding the lines (plain
text or base64). Both marker payload forms are accepted:
`value@@@line@@@class@@@methodDesc@@@callIndex@@@typeDesc@@@sourceFile` and the old
`value@@@line@@@class@@@methodDesc`. The producer defaults to `SWAT` / `unknown`.

The Java tool's command line keeps working unchanged (`witnesscreator` replaces
`java -jar WitnessCreator.jar`):

```sh
witnesscreator <base64> [<dir>] [--input PATH]... [--property FILE.prp] [--out DIR] [--producer-version V]
```

`<dir>` is both the (only) input and the default output directory; an empty `<base64>`
yields the default violation witness without waypoints.

## Development

```sh
pip install -e '.[test]'
python -m pytest                      # unit, golden and CLI tests
WITNESSLINT="python /path/to/sv-witnesses/linter/witnesslinter.py" python -m pytest   # also lint the generated witnesses
python -m build                       # wheel + sdist in dist/
python tools/build_pyz.py             # dist/witnesscreator.pyz
```

The golden tests run on copies of SV-COMP tasks in `tests/fixtures/` (see the README there);
generated witnesses are parsed with PyYAML / ElementTree and, when WitnessLint is available
(`$WITNESSLINT` or the CI setup), checked with it.

## Release

Push a version tag such as `v1.0.0`. The CI workflow runs the tests on Python 3.10, 3.13
and 3.14, builds the wheel, the sdist and `witnesscreator.pyz`, and attaches them together
with `SHA256SUMS` to the GitHub release for that tag.

## Migrating from the Java version (0.x)

Version 1.0 replaces the Java/Gradle implementation; there is no jar and no
`witnesses/*.st` template directory any more.

- Replace `java -jar build/libs/WitnessCreator.jar ARGS` by `witnesscreator ARGS` (or
  `python3 witnesscreator.pyz ARGS`); the arguments are unchanged. The tool no longer needs to
  run from a particular working directory.
- Output files and their names (`witness.yml`, `witness.graphml`) are unchanged. Differences in
  content: GraphML assumptions are now `\result = <value>;` / `\result.equals("...");` instead
  of a variable name guessed from the source line, all GraphML text is XML-escaped, and the
  graph carries `sourcecodelang` and `specification`. Strings and chars escape every
  non-ASCII character (`\uXXXX`) in Java literals, YAML scalars are plain ASCII.
- Target resolution is stricter: a stack frame only becomes the target when its package
  matches the file (path or `package` declaration); JDK and SWAT frames are skipped.
- Progress messages are written to stderr (logging) instead of stdout.
- Prefer the library API or the event file over the markers for new integrations.
