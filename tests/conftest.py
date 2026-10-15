import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GRAPHML_NS = "{http://graphml.graphdrawing.org/xmlns}"

# WitnessLint: a command prefix in $WITNESSLINT (e.g. "python3 /path/lint/witnesslinter.py"),
# or the developer's local installation.
_LOCAL_LINT = Path("/home/nils/dev/sv-comp-validators")
_LOCAL_LINT_CMD = [str(_LOCAL_LINT / "venv/bin/python"), str(_LOCAL_LINT / "witnesslint-2.3/lint/witnesslinter.py")]


def witnesslint_command():
    env = os.environ.get("WITNESSLINT")
    if env:
        return env.split()
    if all(Path(p).exists() for p in _LOCAL_LINT_CMD):
        return _LOCAL_LINT_CMD
    return None


@pytest.fixture(scope="session")
def fixtures():
    return FIXTURES


@pytest.fixture
def witnesslint():
    """Runs WitnessLint on a YAML witness; skips the test when the linter is unavailable."""
    cmd = witnesslint_command()
    if cmd is None:
        pytest.skip("WitnessLint not available (set $WITNESSLINT)")

    def run(witness: Path, *programs: Path) -> str:
        p = subprocess.run(
            cmd + ["--expectViolationWitness", "--expectedWitnessVersion", "2", "--witness", str(witness)]
            + [str(x) for x in programs],
            capture_output=True, text=True, timeout=300,
        )
        out = p.stdout + p.stderr
        assert p.returncode == 0 and "finished with exit code 0" in out, out
        return out

    return run


def load_yaml(path: Path):
    """Parses the witness with PyYAML and checks the basic 2.3 structure."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, list) and len(doc) == 1
    entry = doc[0]
    assert entry["entry_type"] == "violation_sequence"
    md = entry["metadata"]
    assert md["format_version"] == "2.3"
    assert md["task"]["language"] == "Java"
    assert "data_model" not in md["task"]
    assert set(md["task"]["input_file_hashes"]) == set(md["task"]["input_files"])
    for seg in entry["content"]:
        wps = seg["segment"]
        assert len(wps) == 1
        wp = wps[0]["waypoint"]
        assert wp["action"] == "follow"
        assert wp["location"]["line"] >= 1
        assert wp["location"]["file_name"] in md["task"]["input_files"], wp
        if "column" in wp["location"]:
            assert wp["location"]["column"] >= 1
        if wp["type"] == "function_return":
            assert wp["constraint"]["format"] == "java_expression"
        else:
            assert wp["type"] == "target" and "constraint" not in wp
    return entry


def waypoints(entry):
    return [seg["segment"][0]["waypoint"] for seg in entry["content"]]


def assert_single_final_target(entry):
    """Exactly one target waypoint, and it is the last segment (WitnessLint does not check this)."""
    wps = waypoints(entry)
    targets = [i for i, wp in enumerate(wps) if wp["type"] == "target"]
    assert targets == [len(wps) - 1], [wp["type"] for wp in wps]


def load_graphml(path: Path):
    root = ET.parse(path).getroot()
    graph = root.find(GRAPHML_NS + "graph")
    data = {d.get("key"): d.text for d in graph.findall(GRAPHML_NS + "data")}
    nodes = {n.get("id"): {d.get("key"): d.text for d in n.findall(GRAPHML_NS + "data")} for n in graph.findall(GRAPHML_NS + "node")}
    edges = []
    for e in graph.findall(GRAPHML_NS + "edge"):
        d = {x.get("key"): x.text for x in e.findall(GRAPHML_NS + "data")}
        d["source"], d["target"] = e.get("source"), e.get("target")
        edges.append(d)
    return data, nodes, edges


def cli(*args, cwd=None):
    """Runs the command line interface in a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "witnesscreator", *map(str, args)],
        capture_output=True, text=True, cwd=cwd,
    )


@pytest.fixture
def task_dir(tmp_path):
    """A copy of a fixture task directory (so tests may write next to it)."""

    def copy(name: str) -> Path:
        dst = tmp_path / Path(name).name
        shutil.copytree(FIXTURES / name, dst)
        return dst

    return copy
