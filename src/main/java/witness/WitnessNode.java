package witness;

import java.util.LinkedHashMap;
import java.util.Map;

public class WitnessNode {
    private final int id;
    private final Map<String, String> data = new LinkedHashMap<>();

    public WitnessNode(int id) {
        this.id = id;
    }

    public int getId() {
        return id;
    }

    public Map<String, String> getData() {
        return data;
    }

    public void addData(String key, String value) {
        data.put(key, value);
    }
}
