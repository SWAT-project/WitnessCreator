# WitnessCreator

WitnessCreator creates SV-COMP violation witnesses from SWAT witness markers:

- `witness.yml` in the [YAML witness format 2.3](https://gitlab.com/sosy-lab/benchmarking/sv-witnesses)
  for Java (one `violation_sequence` with a `function_return` waypoint per
  `Verifier.nondet*()` value and a final `target` waypoint at the violating statement),
- `witness.graphml` in the legacy GraphML format, for validators that still consume it.

## Usage

```sh
java -jar build/libs/WitnessCreator.jar <markers> [<dir>] \
    [--input <path>]... [--property <file.prp>] [--out <dir>] [--producer-version <version>]
```

- `<markers>`: base64 of the SWAT output lines carrying `[WITNESS]` (one per nondet value:
  `value@@@line@@@class@@@method@@@callIndex@@@typeDesc@@@sourceFile`) and `[WITNESS_TARGET]`
  (the uncaught throwable with its stack trace) markers. An empty string yields the default
  violation witness without waypoints.
- `--input`: the task's input files or directories exactly as given to the verifier. They are
  searched for the sources (`.java`) and listed, with their SHA-256 hashes, in the witness.
- `--property`: the property file, its content becomes the witness' `specification`.
- `--out`: the output directory (default: `<dir>`, the legacy positional source directory).
- `--producer-version`: written to `metadata.producer.version`.

Columns are derived from the sources: a `function_return` waypoint points to the closing
parenthesis of the `callIndex`-th nondet call on its line, the `target` waypoint to the start of
the violating statement (`assert`, `throw`, or the first token of the innermost statement in the
task sources that appears in the stack trace).

## Build

```sh
./gradlew --no-daemon clean build
```

The release archive is written to `build/distributions/` and contains the
runtime layout expected by SWAT:

```text
WitnessCreator/
  build/libs/WitnessCreator.jar
  witnesses/default_violation.st
  witnesses/witness.st
```

## Release

Push a version tag such as `v0.1.0`. The CI workflow builds
`witness-creator-<version>.zip`, uploads it as a CI artifact, and attaches it to
the GitHub release for that tag together with `SHA256SUMS`.
