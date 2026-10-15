import base64
import shutil

import yaml

from conftest import cli, load_graphml, load_yaml, waypoints
from witnesscreator import Frame, Location, NondetReturn, Violation, dump_events
from witnesscreator.cli import main


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def marker(kind: str, payload: str) -> str:
    return f"prefix {kind} {b64(payload)}"


def write_task(dir_):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "Main.java").write_text(
        "import org.sosy_lab.sv_benchmarks.Verifier;\n"
        "public class Main {\n"
        "  public static void main(String[] args) {\n"
        "    int x = Verifier.nondetInt();\n"
        "    String s = Verifier.nondetString();\n"
        "    if (x == 3 && s.equals(\"a\\\"b\")) {\n"
        "      assert false;\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    prp = dir_.parent / "valid-assert.prp"
    prp.write_text("CHECK( init(Main.main()), LTL(G assert) )\n")
    return prp


MARKERS = "\n".join([
    marker("[WITNESS]", "3@@@4@@@Main@@@main([Ljava/lang/String;)V@@@0@@@I@@@Main.java"),
    marker("[WITNESS]", "a\"b@@@5@@@Main@@@main([Ljava/lang/String;)V@@@0@@@Ljava/lang/String;@@@Main.java"),
    marker("[WITNESS_TARGET]", "java.lang.AssertionError@@@Main@@Main.java@@7"),
])


def check_witness(out, task):
    entry = load_yaml(out / "witness.yml")
    wps = waypoints(entry)
    assert [wp["type"] for wp in wps] == ["function_return", "function_return", "target"]
    assert wps[0]["constraint"]["value"] == "\\result == 3"
    assert wps[0]["location"] == {"file_name": f"{task}/Main.java", "line": 4, "column": 32}
    assert wps[1]["constraint"]["value"] == '\\result.equals("a\\"b")'
    assert wps[1]["location"]["column"] == 38
    assert wps[2]["location"] == {"file_name": f"{task}/Main.java", "line": 7, "column": 7}
    _, nodes, edges = load_graphml(out / "witness.graphml")
    assert [e["assumption"] for e in edges] == ["\\result = 3;", '\\result.equals("a\\"b");']
    assert edges[0]["assumption.scope"] == "java::LMain;.main([Ljava/lang/String;)V"
    assert edges[0]["originfile"] == "Main.java"
    assert nodes["n2"] == {"violation": "true"}


def test_java_compatible_command_line(tmp_path):
    task = tmp_path / "task"
    prp = write_task(task)
    out = tmp_path / "out"
    p = cli(b64(MARKERS), "--input", task, "--property", prp, "--out", out, "--producer-version", "test")
    assert p.returncode == 0, p.stderr
    entry = load_yaml(out / "witness.yml")
    assert entry["metadata"]["producer"] == {"name": "SWAT", "version": "test"}
    assert entry["metadata"]["task"]["specification"] == "CHECK( init(Main.main()), LTL(G assert) )"
    check_witness(out, task)
    assert "Writing violation witness" in p.stderr


def test_legacy_positional_dir(tmp_path):
    task = tmp_path / "task"
    write_task(task)
    assert main([b64(MARKERS), str(task)]) == 0
    check_witness(task, task)
    entry = load_yaml(task / "witness.yml")
    assert entry["metadata"]["producer"] == {"name": "SWAT", "version": "unknown"}
    assert entry["metadata"]["task"]["specification"] == "CHECK( init(Main.main()), LTL(G assert) )"


def test_legacy_subcommand_with_markers_file(tmp_path):
    task = tmp_path / "task"
    prp = write_task(task)
    markers = tmp_path / "markers.txt"
    markers.write_text(MARKERS + "\n")
    out = tmp_path / "out"
    assert main(["legacy", "--markers-file", str(markers), "--input", str(task), "--property", str(prp),
                 "--out-dir", str(out), "--producer-name", "Other", "--producer-version", "1"]) == 0
    check_witness(out, task)
    assert load_yaml(out / "witness.yml")["metadata"]["producer"] == {"name": "Other", "version": "1"}
    # the file may hold the base64 blob as well
    markers.write_text(b64(MARKERS))
    out2 = tmp_path / "out2"
    assert main(["legacy", "--markers-file", str(markers), "--input", str(task), "--out-dir", str(out2), "--format", "yaml"]) == 0
    assert (out2 / "witness.yml").exists() and not (out2 / "witness.graphml").exists()


def test_legacy_empty_markers_write_default_violation(tmp_path):
    task = tmp_path / "task"
    write_task(task)
    out = tmp_path / "out"
    p = cli("", "--input", task, "--out", out)
    assert p.returncode == 0, p.stderr
    entry = load_yaml(out / "witness.yml")
    assert entry["content"] == []
    _, nodes, edges = load_graphml(out / "witness.graphml")
    assert nodes["n0"] == {"entry": "true", "violation": "true"} and edges == []
    # a target alone yields a single final target segment
    p = cli(b64(marker("[WITNESS_TARGET]", "java.lang.AssertionError@@@Main@@Main.java@@7")), "--input", task, "--out", out)
    assert p.returncode == 0
    wps = waypoints(load_yaml(out / "witness.yml"))
    assert len(wps) == 1 and wps[0]["type"] == "target" and wps[0]["location"]["column"] == 7


def test_legacy_four_field_markers(tmp_path):
    (tmp_path / "Main.java").write_text("class Main {\n  int x = Verifier.nondetInt();\n}\n")
    markers = marker("[WITNESS]", "1@@@2@@@Main@@@<init>()V")
    assert main([b64(markers), str(tmp_path)]) == 0
    wps = waypoints(load_yaml(tmp_path / "witness.yml"))
    assert wps[0]["constraint"]["value"] == "\\result == 1"
    assert wps[0]["location"]["line"] == 2 and wps[0]["location"]["column"] == 30
    text = (tmp_path / "witness.graphml").read_text()
    assert "&lt;init&gt;" in text
    _, _, edges = load_graphml(tmp_path / "witness.graphml")
    assert edges[0]["assumption.scope"] == "java::LMain;.<init>()V"


def test_events_command(tmp_path):
    task = tmp_path / "task"
    prp = write_task(task)
    values = [
        NondetReturn("nondetInt", "int", "3", Location(class_name="Main", source_file="Main.java", line=4, call_index=0, method="main([Ljava/lang/String;)V")),
        NondetReturn("nondetString", "String", 'a"b', Location(file_name=f"{task}/Main.java", line=5, column=38)),
    ]
    violation = Violation("java.lang.AssertionError", [Frame("Main", "Main.java", 7)])
    events = tmp_path / "events.jsonl"
    events.write_text(dump_events(values, violation, "SWAT", "svcomp27"))
    out = tmp_path / "out"
    p = cli("events", "--events", events, "--property", prp, "--input", task, "--out-dir", out)
    assert p.returncode == 0, p.stderr
    entry = load_yaml(out / "witness.yml")
    assert entry["metadata"]["producer"] == {"name": "SWAT", "version": "svcomp27"}
    wps = waypoints(entry)
    assert wps[0]["location"]["column"] == 32 and wps[1]["location"]["column"] == 38
    assert wps[2]["type"] == "target"
    _, _, edges = load_graphml(out / "witness.graphml")
    assert edges[0]["assumption.scope"] == "java::LMain;.main([Ljava/lang/String;)V"
    assert edges[1]["assumption.scope"] == "java::LMain;"
    # command line overrides the header
    p = cli("events", "--events", events, "--property", prp, "--input", task, "--out-dir", out,
            "--producer-name", "X", "--producer-version", "Y", "--format", "graphml")
    assert p.returncode == 0
    data, _, _ = load_graphml(out / "witness.graphml")
    assert data["producer"] == "X"


def test_events_missing_file_still_writes(tmp_path):
    task = tmp_path / "task"
    write_task(task)
    out = tmp_path / "out"
    p = cli("events", "--events", tmp_path / "nope.jsonl", "--input", task, "--out-dir", out)
    assert p.returncode == 0
    assert "Could not read event file" in p.stderr
    assert load_yaml(out / "witness.yml")["content"] == []
    assert "No property file given" in p.stderr


def test_usage_errors(tmp_path):
    assert cli().returncode == 2
    assert cli("events").returncode == 2
    assert cli("legacy", "--format", "xml").returncode == 2
    p = cli("--version")
    assert p.returncode == 0 and "witnesscreator" in p.stdout
    assert cli("--help").returncode == 0
    assert cli("legacy", "--help").returncode == 0


def test_nothing_written_is_exit_1(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    p = cli("", "--out", blocker / "out")
    assert p.returncode == 1
    assert "Could not" in p.stderr


def test_quiet_and_verbose(tmp_path):
    task = tmp_path / "task"
    write_task(task)
    p = cli("-q", "legacy", b64(MARKERS), str(task))
    assert p.returncode == 0 and "INFO" not in p.stderr
    p = cli("-v", "legacy", b64(MARKERS), str(task))
    assert p.returncode == 0 and "INFO" in p.stderr


def test_pyz_build_and_run(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    tool = Path(__file__).resolve().parent.parent / "tools" / "build_pyz.py"
    pyz = tmp_path / "witnesscreator.pyz"
    assert subprocess.run([sys.executable, str(tool), str(pyz)], capture_output=True).returncode == 0
    task = tmp_path / "task"
    write_task(task)
    p = subprocess.run([sys.executable, str(pyz), b64(MARKERS), str(task)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    check_witness(task, task)
    p = subprocess.run([sys.executable, str(pyz), "--version"], capture_output=True, text=True)
    assert p.stdout.startswith("witnesscreator ")
