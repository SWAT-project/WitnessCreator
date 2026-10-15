package witness;

import java.io.IOException;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * A violation witness in the YAML format, version 2.3, for Java (see
 * https://gitlab.com/sosy-lab/benchmarking/sv-witnesses). The witness is a single
 * {@code violation_sequence} whose segments each hold one {@code follow} waypoint: one
 * {@code function_return} waypoint per recorded {@code Verifier.nondet*()} value and, if the
 * violating statement is known, a final {@code target} waypoint.
 */
public final class YamlWitness {
    public static final String FORMAT_VERSION = "2.3";

    /** A follow waypoint. */
    public static final class Waypoint {
        private final String type;
        private final String constraint;
        private final String fileName;
        private final int line;
        private final Integer column;

        private Waypoint(String type, String constraint, String fileName, int line, Integer column) {
            this.type = type;
            this.constraint = constraint;
            this.fileName = fileName;
            this.line = line;
            this.column = column;
        }

        public static Waypoint functionReturn(
                String constraint, String fileName, int line, Integer column) {
            return new Waypoint("function_return", constraint, fileName, line, column);
        }

        public static Waypoint target(String fileName, int line, Integer column) {
            return new Waypoint("target", null, fileName, line, column);
        }

        public String getType() {
            return type;
        }

        @Override
        public String toString() {
            return type
                    + " @ "
                    + fileName
                    + ":"
                    + line
                    + (column == null ? "" : ":" + column)
                    + (constraint == null ? "" : " [" + constraint + "]");
        }
    }

    private final String producerName;
    private final String producerVersion;
    private final String specification;
    private final SourceFiles sourceFiles;
    private final List<Waypoint> waypoints = new ArrayList<>();

    public YamlWitness(
            String producerName,
            String producerVersion,
            String specification,
            SourceFiles sourceFiles) {
        this.producerName = producerName;
        this.producerVersion = producerVersion;
        this.specification = specification;
        this.sourceFiles = sourceFiles;
    }

    public void add(Waypoint waypoint) {
        waypoints.add(waypoint);
    }

    public List<Waypoint> getWaypoints() {
        return waypoints;
    }

    public String render() throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("- entry_type: \"violation_sequence\"\n");
        sb.append("  metadata:\n");
        sb.append("    format_version: ").append(quote(FORMAT_VERSION)).append('\n');
        sb.append("    uuid: ").append(quote(UUID.randomUUID().toString())).append('\n');
        String time =
                ZonedDateTime.now(ZoneOffset.UTC)
                        .format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'"));
        sb.append("    creation_time: ").append(quote(time)).append('\n');
        sb.append("    producer:\n");
        sb.append("      name: ").append(quote(producerName)).append('\n');
        sb.append("      version: ").append(quote(producerVersion)).append('\n');
        sb.append("    task:\n");
        if (sourceFiles.isEmpty()) {
            sb.append("      input_files: []\n");
            sb.append("      input_file_hashes: {}\n");
        } else {
            sb.append("      input_files:\n");
            for (SourceFiles.InputFile f : sourceFiles.getFiles()) {
                sb.append("      - ").append(quote(f.getDisplayPath())).append('\n');
            }
            sb.append("      input_file_hashes:\n");
            for (SourceFiles.InputFile f : sourceFiles.getFiles()) {
                sb.append("        ")
                        .append(quote(f.getDisplayPath()))
                        .append(": ")
                        .append(quote(f.getSha256()))
                        .append('\n');
            }
        }
        sb.append("      specification: ").append(quote(specification)).append('\n');
        sb.append("      language: \"Java\"\n");
        if (waypoints.isEmpty()) {
            sb.append("  content: []\n");
            return sb.toString();
        }
        sb.append("  content:\n");
        for (Waypoint wp : waypoints) {
            sb.append("  - segment:\n");
            sb.append("    - waypoint:\n");
            sb.append("        type: ").append(quote(wp.type)).append('\n');
            sb.append("        action: \"follow\"\n");
            if (wp.constraint != null) {
                sb.append("        constraint:\n");
                sb.append("          value: ").append(quote(wp.constraint)).append('\n');
                sb.append("          format: \"java_expression\"\n");
            }
            sb.append("        location:\n");
            sb.append("          file_name: ").append(quote(wp.fileName)).append('\n');
            sb.append("          line: ").append(wp.line).append('\n');
            if (wp.column != null) {
                sb.append("          column: ").append(wp.column).append('\n');
            }
        }
        return sb.toString();
    }

    /** Renders a YAML double-quoted scalar. */
    static String quote(String s) {
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
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
