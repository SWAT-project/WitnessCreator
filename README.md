# WitnessCreator

WitnessCreator creates SV-COMP GraphML violation witnesses from SWAT witness
markers.

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
