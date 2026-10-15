import json

from witnesscreator import Frame, Location, NondetReturn, Violation, dump_events, parse_events, read_events
from witnesscreator.events import nondet_return_from_dict, nondet_return_to_dict, violation_to_dict


def test_round_trip(tmp_path):
    values = [
        NondetReturn("nondetInt", "int", "42", Location(class_name="pkg.Main", source_file="Main.java", line=12, call_index=1)),
        NondetReturn("nondetString", "String", "a\"b\nä", Location(file_name="Main.java", line=13, column=27), bits=None),
        NondetReturn("nondetFloat", "float", "0.1", Location(class_name="Main", line=14), bits="0x3dcccccd"),
    ]
    violation = Violation("java.lang.AssertionError", [Frame("pkg.Main", "Main.java", 17), Frame("java.lang.Thread", None, -1)])
    text = dump_events(values, violation, "SWAT", "svcomp27")
    lines = text.splitlines()
    header = json.loads(lines[0])
    assert header == {"kind": "header", "schema": "witnesscreator-events", "version": 1, "producer": {"name": "SWAT", "version": "svcomp27"}}
    assert json.loads(lines[1])["kind"] == "nondet_return"
    assert json.loads(lines[1])["location"]["class_name"] == "pkg.Main"
    assert json.loads(lines[-1])["kind"] == "violation"

    path = tmp_path / "events.jsonl"
    path.write_text(text, encoding="utf-8")
    ev = read_events(path)
    assert ev.producer_name == "SWAT" and ev.producer_version == "svcomp27"
    assert ev.values == values
    assert ev.violation == violation


def test_dict_forms():
    nr = NondetReturn("nondetInt", "int", "1", Location(line=3))
    d = nondet_return_to_dict(nr)
    assert d["kind"] == "nondet_return" and d["bits"] is None and d["location"]["line"] == 3
    assert nondet_return_from_dict(d) == nr
    v = violation_to_dict(Violation("x", []))
    assert v == {"kind": "violation", "throwable": "x", "frames": []}


def test_lenient_parsing():
    lines = [
        "",
        "not json",
        "[1, 2]",
        '{"kind": "header", "schema": "other", "version": 99}',
        '{"kind": "nondet_return", "type": "int", "value": 7, "location": {"line": "4", "call_index": null, "column": 0}}',
        '{"kind": "nondet_return", "value": "x"}',
        '{"kind": "violation", "throwable": "A", "frames": [{"class_name": "Main", "line": "x"}, "junk"]}',
        '{"kind": "violation", "throwable": "B", "frames": null}',
        '{"kind": "mystery"}',
    ]
    ev = parse_events(lines)
    assert ev.header["version"] == 99
    assert ev.producer_name is None
    assert len(ev.values) == 2
    assert ev.values[0].value == "7" and ev.values[0].location.line == 4
    assert ev.values[0].location.call_index == 0 and ev.values[0].location.column is None
    assert ev.values[1].location == Location()
    assert ev.violation.throwable == "B" and ev.violation.frames == []


def test_header_without_producer():
    assert json.loads(dump_events([], None).splitlines()[0]) == {"kind": "header", "schema": "witnesscreator-events", "version": 1}
