package witness;

public class WitnessAssumption {
    private final String value;
    private final String clazz;
    private final String scope;
    private final int line;

    public WitnessAssumption(String value, String clazz, String scope, int line) {
        this.value = value;
        this.clazz = clazz;
        this.scope = scope;
        this.line = line;
    }

    public String getScope() {
        return scope;
    }

    public String getValue() {
        return value;
    }

    public String getClazz() {
        return clazz;
    }

    public int getLine() {
        return line;
    }
}
