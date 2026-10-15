import pytest

from witnesscreator.literals import (
    char_literal,
    graphml_assumption_value,
    plain_decimal,
    result_constraint,
    string_literal,
    value_from_bits,
)
from witnesscreator.model import normalize_type


def test_integral_types():
    assert result_constraint("5", "int") == "\\result == 5"
    assert result_constraint("-5", "I") == "\\result == -5"
    assert result_constraint("-128", "byte") == "\\result == -128"
    assert result_constraint("32767", "S") == "\\result == 32767"
    assert result_constraint("-2147483648", "int") == "\\result == -2147483648"


def test_longs_get_suffix_only_outside_int_range():
    assert result_constraint("5", "long") == "\\result == 5"
    assert result_constraint("2147483647", "J") == "\\result == 2147483647"
    assert result_constraint("2147483648", "J") == "\\result == 2147483648L"
    assert result_constraint("5000000000", "long") == "\\result == 5000000000L"
    assert result_constraint("-9223372036854775808", "long") == "\\result == -9223372036854775808L"
    assert result_constraint("garbage", "long") == "\\result == garbage"


def test_booleans():
    assert result_constraint("true", "boolean") == "\\result == true"
    assert result_constraint("false", "Z") == "\\result == false"
    assert result_constraint("maybe", "boolean") == "\\result == false"


def test_chars_are_java_literals():
    assert result_constraint("97", "char") == "\\result == 'a'"
    assert result_constraint("39", "C") == "\\result == '\\''"
    assert result_constraint("92", "C") == "\\result == '\\\\'"
    assert result_constraint("10", "C") == "\\result == '\\n'"
    assert result_constraint("0", "C") == "\\result == '\\u0000'"
    assert result_constraint("228", "C") == "\\result == '\\u00e4'"
    assert result_constraint("65535", "C") == "\\result == '\\uffff'"
    assert result_constraint("127", "C") == "\\result == '\\u007f'"
    assert char_literal("x") == "x"
    assert char_literal("70000") == "70000"


def test_floating_point():
    assert result_constraint("1.5", "float") == "\\result == 1.5f"
    assert result_constraint("-0.000002022784", "F") == "\\result == -0.000002022784f"
    assert result_constraint("1.0E10", "F") == "\\result == 10000000000.0f"
    assert result_constraint("1.0E-5", "D") == "\\result == 0.000010"
    assert result_constraint("0.1", "double") == "\\result == 0.1"
    assert result_constraint("-0.0", "D") == "\\result == -0.0"
    assert result_constraint("-0.0", "F") == "\\result == -0.0f"
    assert result_constraint("10000000000", "D") == "\\result == 10000000000.0"
    assert result_constraint("NaN", "float") == "Float.isNaN(\\result)"
    assert result_constraint("NaN", "D") == "Double.isNaN(\\result)"
    assert result_constraint("Infinity", "double") == "\\result == Double.POSITIVE_INFINITY"
    assert result_constraint("-Infinity", "float") == "\\result == Float.NEGATIVE_INFINITY"
    assert result_constraint("1.5f", "F") == "\\result == 1.5f"
    assert result_constraint("nonsense", "D") == "\\result == nonsense.0"


def test_plain_decimal():
    assert plain_decimal("1.0E10") == "10000000000"
    assert plain_decimal("-1.0E-3") == "-0.0010"
    assert plain_decimal("-0.0") == "-0.0"
    assert plain_decimal("1E3") == "1000"
    assert plain_decimal("x") == "x"


def test_strings():
    assert result_constraint("abc", "String") == '\\result.equals("abc")'
    assert result_constraint("", "Ljava/lang/String;") == '\\result.equals("")'
    assert result_constraint('a"b\\c\nd\te', "String") == '\\result.equals("a\\"b\\\\c\\nd\\te")'
    assert result_constraint("\u0001x\u007f", "String") == '\\result.equals("\\u0001x\\u007f")'
    assert result_constraint("\r\b\f", "String") == '\\result.equals("\\r\\b\\f")'


def test_string_literal_escapes_everything_non_ascii():
    assert string_literal("ä€") == '"\\u00e4\\u20ac"'
    # outside the BMP: a surrogate pair, as Java sees it
    assert string_literal("\U0001F600") == '"\\ud83d\\ude00"'
    # a lone surrogate (e.g. from surrogateescape decoding) is representable too
    assert string_literal("\ud800") == '"\\ud800"'
    assert string_literal("\x00\x1f\x85 ") == '"\\u0000\\u001f\\u0085\\u2028"'


def test_legacy_markers_without_type():
    assert result_constraint("42", None) == "\\result == 42"
    assert result_constraint("-7", None) == "\\result == -7"
    assert result_constraint("true", None) == "\\result == true"
    assert result_constraint("hi", None) == '\\result.equals("hi")'
    assert result_constraint("1.5", "unknown-type") == '\\result.equals("1.5")'


def test_normalize_type():
    assert normalize_type("I") == "int"
    assert normalize_type("int") == "int"
    assert normalize_type("Ljava/lang/String;") == "String"
    assert normalize_type("java.lang.String") == "String"
    assert normalize_type(None) is None
    assert normalize_type("Object") is None


def test_value_from_bits():
    assert value_from_bits("0x3dcccccd", "float") == "0.10000000149011612"
    assert value_from_bits("0x3ff0000000000000", "double") == "1.0"
    assert value_from_bits("0x7fc00000", "float") == "NaN"
    assert value_from_bits("0x7f800000", "float") == "Infinity"
    assert value_from_bits("0xfff0000000000000", "double") == "-Infinity"
    assert value_from_bits("0x80000000", "float") == "-0.0"
    assert value_from_bits("0x1", "int") is None
    assert value_from_bits("zz", "float") is None
    assert result_constraint(value_from_bits("0x3dcccccd", "float"), "float") == "\\result == 0.10000000149011612f"


@pytest.mark.parametrize(
    "value, type_, expected",
    [
        ("5", "int", "5"),
        ("5000000000", "long", "5000000000"),
        ("true", "boolean", "true"),
        ("97", "char", "97"),
        ("a", "char", "97"),
        ("1.5", "float", "1.5"),
        ("1.0E10", "double", "10000000000"),
        ("-0.0", "double", "-0.0"),
        ("NaN", "float", "NaN"),
        ("-Infinity", "double", "-Infinity"),
        ("a\"b", "String", '.equals("a\\"b")'),
        ("ä", "String", '.equals("\\u00e4")'),
        ("42", None, "42"),
        ("x", None, '.equals("x")'),
    ],
)
def test_graphml_assumption_value(value, type_, expected):
    assert graphml_assumption_value(value, type_) == expected
