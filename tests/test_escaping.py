import xml.etree.ElementTree as ET

import pytest
import yaml

from witnesscreator.graphml_writer import Assumption, render_graphml, xml_escape
from witnesscreator.yaml_writer import Metadata, Waypoint, render_yaml, yaml_quote


@pytest.mark.parametrize(
    "s",
    [
        "",
        "plain",
        'quote " and backslash \\',
        "\\result == 3",
        "tab\tnewline\ncr\r",
        "\x00\x01\x1f\x7f",
        "\x85\xa0  ",
        "ä€",
        "\U0001F600 emoji",
        "﻿￾￿",
        "\ud800 lone surrogate",
        "a: b # not a comment",
        "- not a list",
    ],
)
def test_yaml_quote_round_trips_through_pyyaml(s):
    quoted = yaml_quote(s)
    assert quoted.isascii()
    assert yaml.safe_load(quoted) == s
    assert yaml.safe_load(f"k: {quoted}\n") == {"k": s}


def test_yaml_quote_escapes():
    assert yaml_quote('\\result.equals("a\\"b")') == '"\\\\result.equals(\\"a\\\\\\"b\\")"'
    assert yaml_quote("ä") == '"\\u00e4"'
    assert yaml_quote("\U0001F600") == '"\\U0001f600"'
    assert yaml_quote("\n\t\r") == '"\\n\\t\\r"'


def test_yaml_document_structure():
    md = Metadata("u", "2026-01-01T00:00:00Z", "P", "v", 'CHECK( init(Main.main()), LTL(G assert) )', [("a/Main.java", "0" * 64)])
    text = render_yaml(md, [Waypoint.function_return('\\result.equals("x")', "a/Main.java", 3, 7), Waypoint.target("a/Main.java", 4, None)])
    doc = yaml.safe_load(text)
    entry = doc[0]
    assert entry["metadata"]["uuid"] == "u"
    assert entry["metadata"]["task"]["input_file_hashes"] == {"a/Main.java": "0" * 64}
    assert entry["metadata"]["task"]["specification"] == "CHECK( init(Main.main()), LTL(G assert) )"
    wps = [s["segment"][0]["waypoint"] for s in entry["content"]]
    assert wps[0]["constraint"] == {"value": '\\result.equals("x")', "format": "java_expression"}
    assert wps[0]["location"] == {"file_name": "a/Main.java", "line": 3, "column": 7}
    assert wps[1] == {"type": "target", "action": "follow", "location": {"file_name": "a/Main.java", "line": 4}}
    assert yaml.safe_load(render_yaml(md, []))[0]["content"] == []
    empty = Metadata("u", "t", "P", "v", "spec", [])
    assert yaml.safe_load(render_yaml(empty, []))[0]["metadata"]["task"]["input_files"] == []


@pytest.mark.parametrize(
    "s, expected",
    [
        ("a < b & c > d \"q\"", "a &lt; b &amp; c &gt; d &quot;q&quot;"),
        ("<init>", "&lt;init&gt;"),
        ("\x00\x01\x0b", "\\u0000\\u0001\\u000b"),
        ("\t\n ok", "\t\n ok"),
        ("￾", "\\ufffe"),
        ("ä", "ä"),
    ],
)
def test_xml_escape(s, expected):
    assert xml_escape(s) == expected


def test_graphml_escapes_all_text_and_parses():
    text = render_graphml(
        "P & Co", "CHECK( <x> )",
        [Assumption("pkg/<Main>.java", 3, '\\result.equals("<a & b>");', "java::Lpkg/Main;.<init>()V")],
    )
    root = ET.fromstring(text)
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    graph = root.find(ns + "graph")
    data = {d.get("key"): d.text for d in graph.findall(ns + "data")}
    assert data["producer"] == "P & Co"
    assert data["specification"] == "CHECK( <x> )"
    assert data["sourcecodelang"] == "Java"
    edge = graph.find(ns + "edge")
    ed = {d.get("key"): d.text for d in edge.findall(ns + "data")}
    assert ed["originfile"] == "pkg/<Main>.java"
    assert ed["assumption"] == '\\result.equals("<a & b>");'
    assert ed["assumption.scope"] == "java::Lpkg/Main;.<init>()V"
    nodes = {n.get("id"): {d.get("key"): d.text for d in n.findall(ns + "data")} for n in graph.findall(ns + "node")}
    assert nodes["n0"] == {"entry": "true"}
    assert nodes["n1"] == {"violation": "true"}
    assert "sink" in nodes


def test_graphml_default_violation():
    root = ET.fromstring(render_graphml("P", None, []))
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    nodes = {n.get("id"): {d.get("key"): d.text for d in n.findall(ns + "data")} for n in root.iter(ns + "node")}
    assert nodes["n0"] == {"entry": "true", "violation": "true"}
    assert not list(root.iter(ns + "edge"))
