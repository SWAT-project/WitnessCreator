package witness;

import java.math.BigDecimal;

/** Renders recorded values as {@code java_expression} constraints over {@code \result}. */
public final class JavaLiterals {
    private static final String RESULT = "\\result";

    private JavaLiterals() {}

    /**
     * The constraint satisfied exactly when the function returned {@code value}.
     *
     * @param value the value as recorded by the executor
     * @param typeDesc the JVM descriptor of the returned type, {@code null} if unknown (legacy)
     */
    public static String resultConstraint(String value, String typeDesc) {
        if (typeDesc == null) {
            return legacyConstraint(value);
        }
        switch (typeDesc) {
            case "Z":
                return RESULT + " == " + ("true".equals(value) ? "true" : "false");
            case "B":
            case "S":
            case "I":
                return RESULT + " == " + value;
            case "J":
                return RESULT + " == " + longLiteral(value);
            case "C":
                return RESULT + " == " + charLiteral(value);
            case "F":
                return floatingConstraint(value, true);
            case "D":
                return floatingConstraint(value, false);
            case "Ljava/lang/String;":
                return RESULT + ".equals(" + stringLiteral(value) + ")";
            default:
                return legacyConstraint(value);
        }
    }

    private static String legacyConstraint(String value) {
        if (value.matches("-?\\d+") || "true".equals(value) || "false".equals(value)) {
            return RESULT + " == " + value;
        }
        return RESULT + ".equals(" + stringLiteral(value) + ")";
    }

    private static String longLiteral(String value) {
        try {
            long l = Long.parseLong(value);
            if (l >= Integer.MIN_VALUE && l <= Integer.MAX_VALUE) {
                return value;
            }
            return value + "L";
        } catch (NumberFormatException e) {
            return value;
        }
    }

    private static String floatingConstraint(String value, boolean isFloat) {
        String box = isFloat ? "Float" : "Double";
        switch (value) {
            case "NaN":
                return box + ".isNaN(" + RESULT + ")";
            case "Infinity":
                return RESULT + " == " + box + ".POSITIVE_INFINITY";
            case "-Infinity":
                return RESULT + " == " + box + ".NEGATIVE_INFINITY";
            default:
                break;
        }
        String literal = value;
        try {
            // Normalises scientific notation and guarantees a decimal point; BigDecimal has no
            // negative zero, so the sign is kept separately
            boolean negative = value.startsWith("-");
            literal = new BigDecimal(negative ? value.substring(1) : value).toPlainString();
            if (negative) {
                literal = "-" + literal;
            }
        } catch (NumberFormatException e) {
            // keep as is
        }
        if (!literal.contains(".")) {
            literal += ".0";
        }
        return RESULT + " == " + literal + (isFloat ? "f" : "");
    }

    /** Char values are recorded as their code point. */
    public static String charLiteral(String codePoint) {
        int c;
        try {
            c = Integer.parseInt(codePoint);
        } catch (NumberFormatException e) {
            return codePoint;
        }
        switch (c) {
            case '\'':
                return "'\\''";
            case '\\':
                return "'\\\\'";
            case '\n':
                return "'\\n'";
            case '\r':
                return "'\\r'";
            case '\t':
                return "'\\t'";
            case '\b':
                return "'\\b'";
            case '\f':
                return "'\\f'";
            default:
                break;
        }
        if (c >= 0x20 && c < 0x7f) {
            return "'" + (char) c + "'";
        }
        return String.format("'\\u%04x'", c);
    }

    public static String stringLiteral(String value) {
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"':
                    sb.append("\\\"");
                    break;
                case '\\':
                    sb.append("\\\\");
                    break;
                case '\n':
                    sb.append("\\n");
                    break;
                case '\r':
                    sb.append("\\r");
                    break;
                case '\t':
                    sb.append("\\t");
                    break;
                case '\b':
                    sb.append("\\b");
                    break;
                case '\f':
                    sb.append("\\f");
                    break;
                default:
                    if (c < 0x20 || c == 0x7f) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.append('"').toString();
    }
}
