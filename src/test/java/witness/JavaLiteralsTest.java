package witness;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class JavaLiteralsTest {

    @Test
    void integralTypes() {
        assertEquals("\\result == 5", JavaLiterals.resultConstraint("5", "I"));
        assertEquals("\\result == -5", JavaLiterals.resultConstraint("-5", "I"));
        assertEquals("\\result == -128", JavaLiterals.resultConstraint("-128", "B"));
        assertEquals("\\result == 32767", JavaLiterals.resultConstraint("32767", "S"));
        assertEquals("\\result == -2147483648", JavaLiterals.resultConstraint("-2147483648", "I"));
    }

    @Test
    void longsGetSuffixOnlyWhenNeeded() {
        assertEquals("\\result == 5", JavaLiterals.resultConstraint("5", "J"));
        assertEquals("\\result == 5000000000L", JavaLiterals.resultConstraint("5000000000", "J"));
        assertEquals(
                "\\result == -9223372036854775808L",
                JavaLiterals.resultConstraint("-9223372036854775808", "J"));
    }

    @Test
    void booleans() {
        assertEquals("\\result == true", JavaLiterals.resultConstraint("true", "Z"));
        assertEquals("\\result == false", JavaLiterals.resultConstraint("false", "Z"));
    }

    @Test
    void charsAreRenderedAsLiterals() {
        assertEquals("\\result == 'a'", JavaLiterals.resultConstraint("97", "C"));
        assertEquals("\\result == '\\''", JavaLiterals.resultConstraint("39", "C"));
        assertEquals("\\result == '\\\\'", JavaLiterals.resultConstraint("92", "C"));
        assertEquals("\\result == '\\n'", JavaLiterals.resultConstraint("10", "C"));
        assertEquals("\\result == '\\u0000'", JavaLiterals.resultConstraint("0", "C"));
        assertEquals("\\result == '\\u00e4'", JavaLiterals.resultConstraint("228", "C"));
        assertEquals("\\result == '\\uffff'", JavaLiterals.resultConstraint("65535", "C"));
    }

    @Test
    void floatingPoint() {
        assertEquals("\\result == 1.5f", JavaLiterals.resultConstraint("1.5", "F"));
        assertEquals("\\result == -0.000002022784f", JavaLiterals.resultConstraint("-0.000002022784", "F"));
        assertEquals("\\result == 10000000000.0f", JavaLiterals.resultConstraint("1.0E10", "F"));
        assertEquals("\\result == 0.1", JavaLiterals.resultConstraint("0.1", "D"));
        assertEquals("\\result == -0.0", JavaLiterals.resultConstraint("-0.0", "D"));
        assertEquals("\\result == 10000000000.0", JavaLiterals.resultConstraint("10000000000", "D"));
        assertEquals("Float.isNaN(\\result)", JavaLiterals.resultConstraint("NaN", "F"));
        assertEquals("Double.isNaN(\\result)", JavaLiterals.resultConstraint("NaN", "D"));
        assertEquals("\\result == Double.POSITIVE_INFINITY", JavaLiterals.resultConstraint("Infinity", "D"));
        assertEquals("\\result == Float.NEGATIVE_INFINITY", JavaLiterals.resultConstraint("-Infinity", "F"));
    }

    @Test
    void strings() {
        assertEquals("\\result.equals(\"abc\")", JavaLiterals.resultConstraint("abc", "Ljava/lang/String;"));
        assertEquals("\\result.equals(\"\")", JavaLiterals.resultConstraint("", "Ljava/lang/String;"));
        assertEquals(
                "\\result.equals(\"a\\\"b\\\\c\\nd\\te\")",
                JavaLiterals.resultConstraint("a\"b\\c\nd\te", "Ljava/lang/String;"));
        assertEquals(
                "\\result.equals(\"\\u0001x\")",
                JavaLiterals.resultConstraint("\u0001x", "Ljava/lang/String;"));
        assertEquals("\\result.equals(\"ä€\")", JavaLiterals.resultConstraint("ä€", "Ljava/lang/String;"));
    }

    @Test
    void legacyMarkersWithoutType() {
        assertEquals("\\result == 42", JavaLiterals.resultConstraint("42", null));
        assertEquals("\\result == true", JavaLiterals.resultConstraint("true", null));
        assertEquals("\\result.equals(\"hi\")", JavaLiterals.resultConstraint("hi", null));
    }
}
