"""Emitter for the legacy GraphML violation witness (format 1.0), as wit4java consumes it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

_XML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def _xml_char_ok(c: int) -> bool:
    return c in (0x9, 0xA, 0xD) or 0x20 <= c <= 0xD7FF or 0xE000 <= c <= 0xFFFD or 0x10000 <= c <= 0x10FFFF


def xml_escape(s: str) -> str:
    """Escapes markup characters; characters XML 1.0 cannot carry become ``\\uXXXX``."""
    out = []
    for ch in str(s):
        esc = _XML_ESCAPES.get(ch)
        if esc is not None:
            out.append(esc)
        elif _xml_char_ok(ord(ch)):
            out.append(ch)
        else:
            out.append(f"\\u{ord(ch):04x}")
    return "".join(out)


@dataclass
class Assumption:
    """One edge of the witness automaton: a value a ``nondet*`` call returned."""

    origin_file: str
    line: int
    text: str
    scope: str


_HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <key attr.name="originFileName" attr.type="string" for="edge" id="originfile">
    <default>&lt;command-line&gt;</default>
  </key>
  <key attr.name="invariant" attr.type="string" for="node" id="invariant"/>
  <key attr.name="invariant.scope" attr.type="string" for="node" id="invariant.scope"/>
  <key attr.name="isViolationNode" attr.type="boolean" for="node" id="violation">
    <default>false</default>
  </key>
  <key attr.name="isEntryNode" attr.type="boolean" for="node" id="entry">
    <default>false</default>
  </key>
  <key attr.name="isSinkNode" attr.type="boolean" for="node" id="sink">
    <default>false</default>
  </key>
  <key attr.name="enterLoopHead" attr.type="boolean" for="edge" id="enterLoopHead">
    <default>false</default>
  </key>
  <key attr.name="cyclehead" attr.type="boolean" for="edge" id="cyclehead">
    <default>false</default>
  </key>
  <key attr.name="threadId" attr.type="int" for="edge" id="threadId">
    <default>0</default>
  </key>
  <key attr.name="createThread" attr.type="int" for="edge" id="createThread">
    <default>0</default>
  </key>
  <key attr.name="sourcecodeLanguage" attr.type="string" for="graph" id="sourcecodelang"/>
  <key attr.name="programFile" attr.type="string" for="graph" id="programfile"/>
  <key attr.name="programHash" attr.type="string" for="graph" id="programhash"/>
  <key attr.name="specification" attr.type="string" for="graph" id="specification"/>
  <key attr.name="architecture" attr.type="string" for="graph" id="architecture"/>
  <key attr.name="producer" attr.type="string" for="graph" id="producer"/>
  <key attr.name="startline" attr.type="int" for="edge" id="startline"/>
  <key attr.name="control" attr.type="string" for="edge" id="control"/>
  <key attr.name="assumption" attr.type="string" for="edge" id="assumption"/>
  <key attr.name="assumption.resultfunction" attr.type="string" for="edge" id="assumption.resultfunction"/>
  <key attr.name="assumption.scope" attr.type="string" for="edge" id="assumption.scope"/>
  <key attr.name="enterFunction" attr.type="string" for="edge" id="enterFunction"/>
  <key attr.name="returnFromFunction" attr.type="string" for="edge" id="returnFrom"/>
  <key attr.name="witness-type" attr.type="string" for="graph" id="witness-type"/>
  <graph edgedefault="directed">
    <data key="witness-type">violation_witness</data>
    <data key="sourcecodelang">Java</data>
"""


def render_graphml(producer: str, specification: Optional[str], assumptions: List[Assumption]) -> str:
    """The witness automaton: a chain of edges, one per assumption, ending in the violation node.

    Without assumptions the automaton is the single entry node that is also the
    violation node (the "default violation").
    """
    out = [_HEADER]
    out.append(f"    <data key=\"producer\">{xml_escape(producer)}</data>\n")
    if specification:
        out.append(f"    <data key=\"specification\">{xml_escape(specification)}</data>\n")
    out.append('    <node id="sink"/>\n')
    if not assumptions:
        out.append('    <node id="n0">\n')
        out.append('      <data key="entry">true</data>\n')
        out.append('      <data key="violation">true</data>\n')
        out.append("    </node>\n")
    else:
        last = len(assumptions)
        for i in range(last + 1):
            out.append(f'    <node id="n{i}">\n')
            if i == 0:
                out.append('      <data key="entry">true</data>\n')
            if i == last:
                out.append('      <data key="violation">true</data>\n')
            out.append("    </node>\n")
        for i, a in enumerate(assumptions):
            out.append(f'    <edge source="n{i}" target="n{i + 1}">\n')
            out.append(f'      <data key="originfile">{xml_escape(a.origin_file)}</data>\n')
            out.append(f'      <data key="startline">{int(a.line)}</data>\n')
            out.append('      <data key="threadId">0</data>\n')
            out.append(f'      <data key="assumption">{xml_escape(a.text)}</data>\n')
            out.append(f'      <data key="assumption.scope">{xml_escape(a.scope)}</data>\n')
            out.append("    </edge>\n")
    out.append("  </graph>\n")
    out.append("</graphml>\n")
    return "".join(out)
