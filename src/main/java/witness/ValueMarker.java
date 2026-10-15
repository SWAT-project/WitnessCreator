package witness;

import java.util.Arrays;
import java.util.Set;

/**
 * A decoded {@code [WITNESS]} marker: one value returned by a {@code Verifier.nondet*()} call.
 *
 * <p>Payload format (fields separated by {@code @@@}):
 * {@code value@@@line@@@className@@@methodDesc@@@callIndex@@@typeDesc@@@sourceFile}.
 * The legacy format {@code value@@@line@@@className@@@methodDesc} is still accepted. Because a
 * String value may itself contain the separator, the fields are parsed from the end.
 */
public final class ValueMarker {
    private static final String SEPARATOR = "@@@";
    private static final Set<String> TYPE_DESCRIPTORS =
            Set.of("Z", "B", "C", "S", "I", "J", "F", "D", "Ljava/lang/String;");

    private final String value;
    private final int line;
    private final String className;
    private final String methodDesc;
    private final int callIndex;
    private final String typeDesc;
    private final String sourceFile;

    private ValueMarker(
            String value,
            int line,
            String className,
            String methodDesc,
            int callIndex,
            String typeDesc,
            String sourceFile) {
        this.value = value;
        this.line = line;
        this.className = className;
        this.methodDesc = methodDesc;
        this.callIndex = callIndex;
        this.typeDesc = typeDesc;
        this.sourceFile = sourceFile;
    }

    public static ValueMarker parse(String payload) {
        String[] parts = payload.split(SEPARATOR, -1);
        int n = parts.length;
        if (n >= 7 && TYPE_DESCRIPTORS.contains(parts[n - 2].trim()) && isInt(parts[n - 3])) {
            return new ValueMarker(
                    join(parts, n - 6),
                    Integer.parseInt(parts[n - 6].trim()),
                    parts[n - 5].trim(),
                    parts[n - 4].trim(),
                    Integer.parseInt(parts[n - 3].trim()),
                    parts[n - 2].trim(),
                    parts[n - 1].trim());
        }
        if (n >= 4 && isInt(parts[n - 3])) {
            return new ValueMarker(
                    join(parts, n - 3),
                    Integer.parseInt(parts[n - 3].trim()),
                    parts[n - 2].trim(),
                    parts[n - 1].trim(),
                    0,
                    null,
                    "");
        }
        throw new IllegalArgumentException("Invalid witness marker: " + payload);
    }

    private static String join(String[] parts, int count) {
        return String.join(SEPARATOR, Arrays.copyOfRange(parts, 0, count));
    }

    private static boolean isInt(String s) {
        try {
            Integer.parseInt(s.trim());
            return true;
        } catch (NumberFormatException e) {
            return false;
        }
    }

    /** The recorded value as printed by the executor (chars as their code point). */
    public String getValue() {
        return value;
    }

    public int getLine() {
        return line;
    }

    /** JVM internal class name of the caller, e.g. {@code pkg/Main$Inner}. */
    public String getClassName() {
        return className;
    }

    public String getMethodDesc() {
        return methodDesc;
    }

    /** 0-based index of the call among the nondet calls on the same source line. */
    public int getCallIndex() {
        return callIndex;
    }

    /** JVM descriptor of the returned type, or {@code null} for legacy markers. */
    public String getTypeDesc() {
        return typeDesc;
    }

    /** The caller's SourceFile attribute, empty if unknown. */
    public String getSourceFile() {
        return sourceFile;
    }

    public boolean isString() {
        return "Ljava/lang/String;".equals(typeDesc);
    }
}
