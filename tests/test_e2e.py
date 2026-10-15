"""Golden end-to-end tests on real SV-COMP tasks (see fixtures/README.md)."""

import logging

import pytest
import yaml

from conftest import FIXTURES, assert_single_final_target, load_graphml, load_yaml, waypoints
from witnesscreator import Frame, Location, NondetReturn, Task, Violation, parse_markers, write_witnesses
from witnesscreator import witness as witness_module

COMMON = FIXTURES / "common"
PROPS = FIXTURES / "properties"
VALID_ASSERT = PROPS / "valid-assert.prp"
NO_RUNTIME_EXCEPTION = PROPS / "no-runtime-exception.prp"


def task_for(task_dir, prp=VALID_ASSERT, **kw):
    return Task(input_files=[str(COMMON), str(task_dir)], property_file=str(prp),
                producer_name="test", producer_version="0", **kw)


def write(task, values, violation, out, **kw):
    paths = write_witnesses(task, values, violation, out, **kw)
    assert set(paths) == {"yaml", "graphml"}
    assert paths["yaml"].read_text(encoding="utf-8").isascii()
    return load_yaml(paths["yaml"]), load_graphml(paths["graphml"])


def test_gdart_example_matches_official_witness(tmp_path, witnesslint):
    """The sv-witnesses example (produced by GDart) for jpf-regression/ExDarko_false."""
    base = FIXTURES / "sv-witnesses"
    inputs = ["./java/common/org/sosy_lab/sv_benchmarks/Verifier.java", "./java/jpf-regression/ExDarko_false/Main.java"]
    task = Task(input_files=inputs, property_file=str(VALID_ASSERT), producer_name="GDart",
                producer_version="VERSION_PLACEHOLDER", base_dir=base)
    main = Location(class_name="Main", source_file="Main.java", line=34, call_index=0)
    values = [
        NondetReturn("nondetInt", "int", "0", main),
        NondetReturn("nondetInt", "int", "0", Location(class_name="Main", source_file="Main.java", line=35, call_index=0)),
    ]
    violation = Violation("java.lang.AssertionError", [Frame("Main", "Main.java", 48), Frame("Main", "Main.java", 35)])
    paths = write_witnesses(task, values, violation, tmp_path)
    ours = load_yaml(paths["yaml"])
    official = yaml.safe_load((base / "ExDarko_false.witness-2.3.yml").read_text(encoding="utf-8"))[0]
    assert ours["content"] == official["content"]
    assert ours["metadata"]["task"] == official["metadata"]["task"]
    assert ours["metadata"]["producer"] == official["metadata"]["producer"]
    assert_single_final_target(ours)
    witnesslint(paths["yaml"], base / "java" / "common", base / "java" / "jpf-regression" / "ExDarko_false")


def test_return2_from_markers(tmp_path, witnesslint):
    """jbmc-regression/return2 with the markers SWAT printed for it."""
    task_dir = FIXTURES / "jbmc-regression" / "return2"
    values, violation = parse_markers(
        "[WITNESS] LTFAQEAxM0BAQE1haW5AQEBtYWluKFtMamF2YS9sYW5nL1N0cmluZzspVkBAQDBAQEBJQEBATWFpbi5qYXZh\n"
        "[WITNESS] MEBAQDE0QEBATWFpbkBAQG1haW4oW0xqYXZhL2xhbmcvU3RyaW5nOylWQEBAMEBAQElAQEBNYWluLmphdmE=\n"
        "[WITNESS_TARGET] amF2YS5sYW5nLkFzc2VydGlvbkVycm9yQEBATWFpbkBATWFpbi5qYXZhQEAxNQ==\n"
    )
    entry, (data, nodes, edges) = write(task_for(task_dir), values, violation, tmp_path)
    md = entry["metadata"]["task"]
    assert md["input_files"] == [f"{COMMON}/org/sosy_lab/sv_benchmarks/Verifier.java", f"{task_dir}/Main.java"]
    assert md["specification"] == "CHECK( init(Main.main()), LTL(G assert) )"
    wps = waypoints(entry)
    assert [(wp["type"], wp["location"]["line"], wp["location"]["column"]) for wp in wps] == [
        ("function_return", 13, 33), ("function_return", 14, 33), ("target", 15, 5)]
    assert [wp["constraint"]["value"] for wp in wps[:2]] == ["\\result == -1", "\\result == 0"]
    assert_single_final_target(entry)
    assert data["producer"] == "test" and data["sourcecodelang"] == "Java"
    assert [(e["originfile"], e["startline"], e["assumption"], e["assumption.scope"]) for e in edges] == [
        ("Main.java", "13", "\\result = -1;", "java::LMain;.main([Ljava/lang/String;)V"),
        ("Main.java", "14", "\\result = 0;", "java::LMain;.main([Ljava/lang/String;)V"),
    ]
    assert nodes["n0"] == {"entry": "true"} and nodes["n2"] == {"violation": "true"}
    witnesslint(tmp_path / "witness.yml", COMMON, task_dir)


def test_float_special_values(tmp_path, witnesslint):
    """jdart-regression/float: NaN, infinities and negative zero."""
    task_dir = FIXTURES / "jdart-regression" / "float"
    loc = lambda line: Location(class_name="Main", source_file="Main.java", line=line, call_index=0, method="main([Ljava/lang/String;)V")
    values = [
        NondetReturn("nondetFloat", "float", "-Infinity", loc(12)),
        NondetReturn("nondetFloat", "float", "NaN", loc(13)),
        NondetReturn("nondetFloat", "float", "-0.0", loc(12)),
        NondetReturn("nondetFloat", "float", "Infinity", loc(13)),
        NondetReturn("nondetFloat", "float", "1.0E10", loc(12)),
        NondetReturn("nondetFloat", "F", "-0.0012512209359556437", loc(13)),
        NondetReturn("nondetFloat", "float", "", loc(12), bits="0x3dcccccd"),
    ]
    violation = Violation("java.lang.AssertionError", [Frame("Main", "Main.java", 14)])
    entry, (_, _, edges) = write(task_for(task_dir), values, violation, tmp_path)
    wps = waypoints(entry)
    assert [wp["constraint"]["value"] for wp in wps[:-1]] == [
        "\\result == Float.NEGATIVE_INFINITY", "Float.isNaN(\\result)", "\\result == -0.0f",
        "\\result == Float.POSITIVE_INFINITY", "\\result == 10000000000.0f", "\\result == -0.0012512209359556437f",
        "\\result == 0.10000000149011612f",
    ]
    assert all(wp["location"]["column"] == 36 for wp in wps[:-1])
    assert wps[-1]["location"] == {"file_name": f"{task_dir}/Main.java", "line": 14, "column": 5}
    assert [e["assumption"] for e in edges] == [
        "\\result = -Infinity;", "\\result = NaN;", "\\result = -0.0;", "\\result = Infinity;",
        "\\result = 10000000000;", "\\result = -0.0012512209359556437;", "\\result = 0.10000000149011612;",
    ]
    assert_single_final_target(entry)
    witnesslint(tmp_path / "witness.yml", COMMON, task_dir)


def test_string_value_and_runtime_exception_thrown_in_jdk(tmp_path, witnesslint):
    """jbmc-regression/StringValueOf08: the NumberFormatException is thrown inside the JDK,
    the target is the innermost frame of the task sources."""
    task_dir = FIXTURES / "jbmc-regression" / "StringValueOf08"
    values = [NondetReturn("nondetString", "String", "fixed", Location(class_name="Main", source_file="Main.java", line=13, call_index=0))]
    violation = Violation("java.lang.NumberFormatException", [
        Frame("jdk.internal.math.FloatingDecimal", "FloatingDecimal.java", 2054),
        Frame("jdk.internal.math.FloatingDecimal", "FloatingDecimal.java", 122),
        Frame("java.lang.Float", "Float.java", 476),
        Frame("Main", "Main.java", 14),
    ])
    entry, (_, _, edges) = write(task_for(task_dir, NO_RUNTIME_EXCEPTION), values, violation, tmp_path)
    assert entry["metadata"]["task"]["specification"] == "CHECK(init(Main.main()), LTL(G ! uncaught(java.lang.RuntimeException)))"
    wps = waypoints(entry)
    assert wps[0]["constraint"]["value"] == '\\result.equals("fixed")'
    assert wps[0]["location"]["column"] == 40
    assert wps[1] == {"type": "target", "action": "follow", "location": {"file_name": f"{task_dir}/Main.java", "line": 14, "column": 5}}
    assert edges[0]["assumption"] == '\\result.equals("fixed");'
    assert_single_final_target(entry)
    witnesslint(tmp_path / "witness.yml", COMMON, task_dir)


def test_multi_file_task_with_package(tmp_path, witnesslint):
    """MinePump/spec1-5_product25: several files, a package directory, the assertion fails in Actions.java."""
    task_dir = FIXTURES / "MinePump" / "spec1-5_product25"
    loc = Location(class_name="Main", source_file="Main.java", line=20, call_index=0, method="getBoolean()Z")
    values = [NondetReturn("nondetBoolean", "boolean", v, loc) for v in ("false", "true", "false")]
    violation = Violation("java.lang.AssertionError", [
        Frame("Actions", "Actions.java", 104), Frame("Actions", "Actions.java", 50), Frame("Main", "Main.java", 50), Frame("Main", "Main.java", 16)])
    entry, (_, _, edges) = write(task_for(task_dir), values, violation, tmp_path)
    files = entry["metadata"]["task"]["input_files"]
    assert files == [
        f"{COMMON}/org/sosy_lab/sv_benchmarks/Verifier.java",
        f"{task_dir}/Actions.java", f"{task_dir}/Main.java",
        f"{task_dir}/MinePumpSystem/Environment.java", f"{task_dir}/MinePumpSystem/MinePump.java",
    ]
    wps = waypoints(entry)
    assert [wp["constraint"]["value"] for wp in wps[:3]] == ["\\result == false", "\\result == true", "\\result == false"]
    assert all(wp["location"] == {"file_name": f"{task_dir}/Main.java", "line": 20, "column": 35} for wp in wps[:3])
    assert wps[3]["location"] == {"file_name": f"{task_dir}/Actions.java", "line": 104, "column": 7}
    assert_single_final_target(entry)
    assert edges[0]["assumption.scope"] == "java::LMain;.getBoolean()Z"
    witnesslint(tmp_path / "witness.yml", COMMON, task_dir)

    # a frame in the package directory resolves through the package path
    violation = Violation("java.lang.RuntimeException", [Frame("MinePumpSystem.MinePump", "MinePump.java", 30)])
    entry, _ = write(task_for(task_dir), [], violation, tmp_path)
    assert waypoints(entry)[0]["location"]["file_name"] == f"{task_dir}/MinePumpSystem/MinePump.java"
    # ... and not when the package does not match
    violation = Violation("java.lang.RuntimeException", [Frame("other.MinePump", "MinePump.java", 30)])
    entry, _ = write(task_for(task_dir), [], violation, tmp_path)
    assert entry["content"] == []


def test_explicit_throw_target(tmp_path):
    task_dir = FIXTURES / "jbmc-regression" / "exceptions16"
    values = [NondetReturn("nondetInt", "int", "7", Location(class_name="Main", source_file="Main.java", line=19, call_index=0))]
    violation = Violation("B", [Frame("Main", "Main.java", 27)])
    entry, _ = write(task_for(task_dir), values, violation, tmp_path)
    wps = waypoints(entry)
    assert wps[0]["location"]["column"] == 32
    assert wps[1]["location"] == {"file_name": f"{task_dir}/Main.java", "line": 27, "column": 7}


def test_inner_class_same_line_calls_unicode_and_package(tmp_path, witnesslint):
    task_dir = FIXTURES / "synthetic"
    main = lambda line, idx=0, cls="Main", src="Main.java": Location(class_name=cls, source_file=src, line=line, call_index=idx)
    values = [
        NondetReturn("nondetChar", "char", "39", main(14)),
        NondetReturn("nondetDouble", "double", "1.0E-5", main(15)),
        NondetReturn("nondetFloat", "float", "0.1", main(16)),
        NondetReturn("nondetLong", "long", "-9223372036854775808", main(17)),
        NondetReturn("nondetString", "String", "a\"b<ä&\U0001F600\x00\n", main(18)),
        NondetReturn("nondetInt", "int", "1", main(9, 0, "Main$Inner")),
        NondetReturn("nondetInt", "int", "2", main(9, 1, "Main$Inner")),
        NondetReturn("nondetInt", "int", "2", main(9, 2, "Main$Inner")),  # no third call on the line
        NondetReturn("nondetInt", "int", "3", main(7, 0, "pkg.Helper", "Helper.java")),
        NondetReturn("nondetBoolean", "boolean", "true", main(29, 0, "Companion")),
    ]
    violation = Violation("java.lang.IllegalStateException", [Frame("Main", "Main.java", 21)])
    entry, (_, _, edges) = write(task_for(task_dir), values, violation, tmp_path)
    wps = waypoints(entry)
    main_java, helper_java = f"{task_dir}/Main.java", f"{task_dir}/pkg/Helper.java"
    assert [(wp["constraint"]["value"], wp["location"]["file_name"], wp["location"]["line"], wp["location"].get("column")) for wp in wps[:-1]] == [
        ("\\result == '\\''", main_java, 14, 34),
        ("\\result == 0.000010", main_java, 15, 38),
        ("\\result == 0.1f", main_java, 16, 36),
        ("\\result == -9223372036854775808L", main_java, 17, 34),
        ('\\result.equals("a\\"b<\\u00e4&\\ud83d\\ude00\\u0000\\n")', main_java, 18, 38),
        ("\\result == 1", main_java, 9, 33),
        ("\\result == 2", main_java, 9, 56),
        ("\\result == 2", main_java, 9, None),
        ("\\result == 3", helper_java, 7, 35),
        ("\\result == true", main_java, 29, 35),
    ]
    assert wps[-1] == {"type": "target", "action": "follow", "location": {"file_name": main_java, "line": 21, "column": 7}}
    assert_single_final_target(entry)
    assert edges[4]["assumption"] == '\\result.equals("a\\"b<\\u00e4&\\ud83d\\ude00\\u0000\\n");'
    assert edges[5]["assumption.scope"] == "java::LMain$Inner;"
    assert edges[8]["originfile"] == "pkg/Helper.java" and edges[8]["assumption.scope"] == "java::Lpkg/Helper;"
    assert edges[0]["assumption"] == "\\result = 39;"
    witnesslint(tmp_path / "witness.yml", COMMON, task_dir)


def test_file_name_locations(tmp_path, caplog):
    task_dir = FIXTURES / "synthetic"
    values = [
        NondetReturn("nondetChar", "char", "97", Location(file_name=f"{task_dir}/Main.java", line=14, column=34)),
        NondetReturn("nondetDouble", "double", "1.5", Location(file_name="Main.java", line=15)),
        NondetReturn("nondetInt", "int", "3", Location(file_name="pkg/Helper.java", line=7, column=0)),
    ]
    entry, (_, _, edges) = write(task_for(task_dir), values, None, tmp_path)
    wps = waypoints(entry)
    assert [(wp["location"]["file_name"], wp["location"].get("column")) for wp in wps] == [
        (f"{task_dir}/Main.java", 34), (f"{task_dir}/Main.java", 38), (f"{task_dir}/pkg/Helper.java", 35)]
    assert [e["assumption.scope"] for e in edges] == ["java::LMain;", "java::LMain;", "java::LHelper;"]
    assert [e["originfile"] for e in edges] == ["Main.java", "Main.java", "pkg/Helper.java"]
    # a file that is not among the inputs is written as given, with a warning
    values = [NondetReturn("nondetInt", "int", "4", Location(file_name="Elsewhere.java", line=1, column=2))]
    with caplog.at_level(logging.WARNING, logger="witnesscreator"):
        text = witness_module.render_yaml(task_for(task_dir), values, None)
    assert "Elsewhere.java is not among the input files" in caplog.text
    wp = yaml.safe_load(text)[0]["content"][0]["segment"][0]["waypoint"]
    assert wp["location"] == {"file_name": "Elsewhere.java", "line": 1, "column": 2}


def test_no_target_warns_but_writes(tmp_path, caplog, witnesslint):
    task_dir = FIXTURES / "jbmc-regression" / "return2"
    values = [NondetReturn("nondetInt", "int", "1", Location(class_name="Main", source_file="Main.java", line=13))]
    with caplog.at_level(logging.WARNING, logger="witnesscreator"):
        entry, _ = write(task_for(task_dir), values, None, tmp_path)
    assert [wp["type"] for wp in waypoints(entry)] == ["function_return"]
    assert "no target waypoint" in caplog.text
    witnesslint(tmp_path / "witness.yml", COMMON, task_dir)

    # all frames outside the task sources (JDK, SWAT's own classes, wrong line, unknown class)
    caplog.clear()
    violation = Violation("java.lang.ArithmeticException", [
        Frame("java.lang.Integer", "Integer.java", 1), Frame("de.uzl.its.swat.Main", "Main.java", 13),
        Frame("Main", "Main.java", 0), Frame("Main", "Main.java", 999), Frame("Nope", "Nope.java", 3), Frame("", None, 3)])
    with caplog.at_level(logging.WARNING, logger="witnesscreator"):
        entry, _ = write(task_for(task_dir), values, violation, tmp_path)
    assert [wp["type"] for wp in waypoints(entry)] == ["function_return"]
    assert "No stack frame of java.lang.ArithmeticException lies in the task sources" in caplog.text


def test_unresolvable_value_location_falls_back_to_package_path(tmp_path, caplog):
    task_dir = FIXTURES / "jbmc-regression" / "return2"
    values = [NondetReturn("nondetInt", "int", "1", Location(class_name="securibench/micro/basic/Basic4", source_file="Basic4.java", line=29, method="doGet()V"))]
    with caplog.at_level(logging.WARNING, logger="witnesscreator"):
        text = witness_module.render_yaml(task_for(task_dir), values, None)
    assert "Could not find the source of securibench/micro/basic/Basic4" in caplog.text
    doc = yaml.safe_load(text)[0]
    wp = doc["content"][0]["segment"][0]["waypoint"]
    assert wp["location"] == {"file_name": "securibench/micro/basic/Basic4.java", "line": 29}
    assert wp["constraint"]["value"] == "\\result == 1"


def test_never_crashes_on_garbage(tmp_path, caplog):
    task = Task(input_files=[str(tmp_path / "missing"), "", str(FIXTURES / "synthetic")], property_file=str(tmp_path / "no.prp"))
    values = [
        NondetReturn(None, None, None, None),
        NondetReturn("x", "weird", "v", Location(line="x")),
        NondetReturn("x", "int", "1", Location(class_name="Main", line=-4)),
        NondetReturn("x", "int", "1", Location(line=3)),
        NondetReturn("x", "int", object(), Location(class_name="Main", source_file="Main.java", line=14, call_index=None, column="?")),
        "not even a value",
    ]
    violation = Violation(None, [None, "junk", Frame(None, None, None), Frame("Main", "Main.java", "x")])
    with caplog.at_level(logging.WARNING, logger="witnesscreator"):
        paths = write_witnesses(task, values, violation, tmp_path)
    assert set(paths) == {"yaml", "graphml"}
    entry = load_yaml(paths["yaml"])
    assert entry["metadata"]["task"]["specification"] == witness_module.DEFAULT_SPECIFICATION
    assert len(entry["content"]) == 1  # the one value with a usable location
    load_graphml(paths["graphml"])
    assert "Ignoring missing input" in caplog.text
    assert "Could not read property file" in caplog.text


def test_formats_are_written_independently(tmp_path, monkeypatch):
    task_dir = FIXTURES / "jbmc-regression" / "return2"

    def boom(*args, **kwargs):
        raise RuntimeError("graphml writer broken")

    monkeypatch.setattr(witness_module, "_render_graphml", boom)
    paths = write_witnesses(task_for(task_dir), [], None, tmp_path)
    assert set(paths) == {"yaml"}
    assert write_witnesses(task_for(task_dir), [], None, tmp_path, formats=("yaml",)) == {"yaml": tmp_path / "witness.yml"}
    assert write_witnesses(task_for(task_dir), [], None, tmp_path, formats=("xml",)) == {}
    assert write_witnesses(task_for(task_dir), [], None, tmp_path, formats=()) == {}


def test_render_functions_and_relative_inputs(tmp_path):
    task = Task(input_files=["../common/", "return2/Main.java"], property_file="../properties/valid-assert.prp",
                base_dir=FIXTURES / "jbmc-regression")
    values = [NondetReturn("nondetInt", "int", "1", Location(class_name="Main", source_file="Main.java", line=13))]
    doc = yaml.safe_load(witness_module.render_yaml(task, values, None))[0]
    assert doc["metadata"]["task"]["input_files"] == ["../common/org/sosy_lab/sv_benchmarks/Verifier.java", "return2/Main.java"]
    assert doc["metadata"]["producer"]["name"] == "witnesscreator"
    assert doc["content"][0]["segment"][0]["waypoint"]["location"]["file_name"] == "return2/Main.java"
    assert "<data key=\"originfile\">Main.java</data>" in witness_module.render_graphml(task, values, None)


@pytest.mark.parametrize("name", ["jbmc-regression/return2", "jdart-regression/float", "MinePump/spec1-5_product25", "synthetic"])
def test_default_violation_lints(tmp_path, witnesslint, name):
    task_dir = FIXTURES / name
    paths = write_witnesses(task_for(task_dir), [], None, tmp_path)
    assert load_yaml(paths["yaml"])["content"] == []
    witnesslint(paths["yaml"], COMMON, task_dir)
