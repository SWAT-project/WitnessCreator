package witness;

public class WitnessEdge {
    private final WitnessNode source;
    private final WitnessAssumption witness;
    private final String assumption;
    private final WitnessNode dest;

    public WitnessEdge(WitnessNode source, WitnessAssumption witness, String assumption, WitnessNode dest) {
        this.source = source;
        this.witness = witness;
        this.assumption = assumption;
        this.dest = dest;
    }

    public WitnessNode getSource() {
        return source;
    }

    public WitnessNode getDest() {
        return dest;
    }

    public WitnessAssumption getWitness() {
        return witness;
    }

    public String getAssumption() {
        return assumption;
    }
}
