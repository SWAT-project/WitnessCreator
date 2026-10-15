import base64

import pytest

from witnesscreator.markers import (
    decode_base64,
    parse_marker_lines,
    parse_markers,
    parse_target_marker,
    parse_value_marker,
)


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def test_parses_current_format():
    m = parse_value_marker("5@@@13@@@pkg/Main$1@@@main([Ljava/lang/String;)V@@@2@@@I@@@Main.java")
    assert m.value == "5"
    assert m.type == "int"
    assert m.function == "nondetInt"
    assert m.location.line == 13
    assert m.location.class_name == "pkg/Main$1"
    assert m.location.method == "main([Ljava/lang/String;)V"
    assert m.location.call_index == 2
    assert m.location.source_file == "Main.java"


def test_string_values_may_contain_the_separator():
    m = parse_value_marker("a@@@b@@@7@@@Main@@@main()V@@@0@@@Ljava/lang/String;@@@Main.java")
    assert m.value == "a@@@b"
    assert m.type == "String"
    assert m.function == "nondetString"
    assert m.location.line == 7
    legacy = parse_value_marker("a@@@b@@@7@@@Main@@@main()V")
    assert legacy.value == "a@@@b"
    assert legacy.location.line == 7


def test_parses_legacy_format():
    m = parse_value_marker("true@@@13@@@Main@@@main([Ljava/lang/String;)V")
    assert m.value == "true"
    assert m.type is None
    assert m.function is None
    assert m.location.line == 13
    assert m.location.class_name == "Main"
    assert m.location.call_index == 0
    assert m.location.source_file is None


def test_empty_source_file_and_types():
    m = parse_value_marker("97@@@3@@@Main@@@m()V@@@0@@@C@@@")
    assert m.type == "char" and m.location.source_file is None
    m = parse_value_marker("1.5@@@3@@@Main@@@m()V@@@0@@@F@@@Main.java")
    assert m.type == "float" and m.function == "nondetFloat"


def test_rejects_garbage():
    with pytest.raises(ValueError):
        parse_value_marker("nonsense")
    with pytest.raises(ValueError):
        parse_value_marker("a@@@b@@@c@@@d")  # line is not a number
    with pytest.raises(ValueError):
        parse_target_marker("no separator")


def test_parses_target():
    t = parse_target_marker(
        "java.lang.AssertionError@@@Main@@Main.java@@23;pkg.Helper$Inner@@Helper.java@@5;java.lang.Thread@@@@-1"
    )
    assert t.is_assertion_error
    assert len(t.frames) == 3
    assert t.frames[0].class_name == "Main"
    assert t.frames[0].source_file == "Main.java"
    assert t.frames[0].line == 23
    assert t.frames[2].source_file is None
    assert t.frames[2].line == -1
    assert parse_target_marker("java.lang.RuntimeException@@@").frames == []
    assert parse_target_marker("x@@@bad;Main@@Main.java@@notanumber").frames[0].line == -1


def test_marker_lines_from_log_output():
    lines = [
        "2026-10-15 10:20:02 [INFO] [SWAT] --> [WITNESS] " + b64("3@@@4@@@Main@@@main([Ljava/lang/String;)V@@@0@@@I@@@Main.java"),
        "unrelated line",
        "[WITNESS] not-base64!!",
        "[WITNESS_TARGET] " + b64("java.lang.AssertionError@@@Main@@Main.java@@7"),
        "[WITNESS] " + b64("a\"b@@@5@@@Main@@@main([Ljava/lang/String;)V@@@0@@@Ljava/lang/String;@@@Main.java"),
    ]
    values, violation = parse_marker_lines(lines)
    assert [v.value for v in values] == ["3", 'a"b']
    assert violation.throwable == "java.lang.AssertionError"
    assert violation.frames[0].line == 7


def test_last_target_wins():
    lines = [
        "[WITNESS_TARGET] " + b64("java.lang.AssertionError@@@Main@@Main.java@@7"),
        "[WITNESS_TARGET] " + b64("java.lang.RuntimeException@@@Main@@Main.java@@9"),
    ]
    _, violation = parse_marker_lines(lines)
    assert violation.throwable == "java.lang.RuntimeException"


def test_parse_markers_accepts_base64_blob_and_plain_text():
    plain = "[WITNESS] " + b64("1@@@2@@@Main@@@<init>()V") + "\n[WITNESS_TARGET] " + b64("java.lang.AssertionError@@@Main@@Main.java@@3")
    for text in (plain, b64(plain), " " + b64(plain) + "\n"):
        values, violation = parse_markers(text)
        assert len(values) == 1 and violation is not None
    assert parse_markers("") == ([], None)
    assert parse_markers("   ") == ([], None)
    assert parse_markers("not markers at all") == ([], None)
    assert parse_markers(None) == ([], None)


def test_decode_base64_is_lenient():
    assert decode_base64(b64("abc")) == "abc"
    assert decode_base64("YWJj") == "abc"
    assert decode_base64("YWJjZA") == "abcd"  # missing padding
    assert decode_base64("YW Jj\n") == "abc"  # whitespace
    assert decode_base64(base64.urlsafe_b64encode(b"\xfb\xff").decode()) == "��"  # url-safe, bad utf-8 replaced
    assert decode_base64("!!!") == ""  # nothing but junk decodes to nothing
