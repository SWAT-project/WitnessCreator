import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.stringtemplate.v4.ST;
import org.stringtemplate.v4.STGroup;
import org.stringtemplate.v4.STRawGroupDir;

import witness.JavaLiterals;
import witness.SourceFiles;
import witness.SourceFiles.InputFile;
import witness.TargetMarker;
import witness.ValueMarker;
import witness.WitnessAssumption;
import witness.WitnessEdge;
import witness.WitnessNode;
import witness.YamlWitness;
import witness.YamlWitness.Waypoint;

/**
 * Creates SV-COMP violation witnesses from SWAT's witness markers.
 *
 * <pre>
 * App &lt;markers&gt; [&lt;dir&gt;] [--input &lt;path&gt;]... [--property &lt;file.prp&gt;] [--out &lt;dir&gt;]
 *     [--producer-version &lt;version&gt;]
 * </pre>
 *
 * <ul>
 *   <li>{@code markers}: base64 of the output lines carrying {@code [WITNESS]} and
 *       {@code [WITNESS_TARGET]} markers (empty for the default violation witness).
 *   <li>{@code dir}: legacy positional argument, the directory holding the task sources; also
 *       the output directory unless {@code --out} is given.
 *   <li>{@code --input}: the task's input files or directories exactly as given to the verifier,
 *       used for the source lookup, the witness' {@code input_files} and their hashes.
 *   <li>{@code --property}: the property file, its content is the witness' specification.
 * </ul>
 *
 * Writes {@code witness.yml} (format 2.3) and, for the validators still consuming GraphML,
 * {@code witness.graphml}.
 */
public class App {

    private static final String PRODUCER = "SWAT";
    private static final String DEFAULT_SPECIFICATION = "CHECK( init(Main.main()), LTL(G assert) )";
    private static final Pattern NONDET_CALL = Pattern.compile("nondet[A-Za-z0-9_]*\\s*\\(");
    private static final Pattern ASSERT_KEYWORD = Pattern.compile("\\bassert\\b");
    private static final Pattern THROW_KEYWORD = Pattern.compile("\\bthrow\\b");

    private final SourceFiles sourceFiles;
    private final Path outDir;

    private App(SourceFiles sourceFiles, Path outDir) {
        this.sourceFiles = sourceFiles;
        this.outDir = outDir;
    }

    public static void main(String[] args) throws IOException {
        List<String> positional = new ArrayList<>();
        List<String> inputs = new ArrayList<>();
        String property = null;
        String out = null;
        String producerVersion = "unknown";
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--input" -> inputs.add(args[++i]);
                case "--property" -> property = args[++i];
                case "--out" -> out = args[++i];
                case "--producer-version" -> producerVersion = args[++i];
                default -> positional.add(args[i]);
            }
        }
        if (positional.isEmpty()) {
            System.err.println(
                    "Usage: App <markers> [<dir>] [--input <path>]... [--property <file.prp>]"
                            + " [--out <dir>] [--producer-version <version>]");
            System.exit(2);
        }
        String markers = positional.get(0);
        String legacyDir = positional.size() > 1 ? positional.get(1) : null;
        if (inputs.isEmpty() && legacyDir != null) {
            inputs.add(legacyDir);
        }
        if (out == null) {
            out = legacyDir != null ? legacyDir : ".";
        }
        Path outDir = Paths.get(out);
        Files.createDirectories(outDir);
        System.out.println("inputs: " + inputs);
        System.out.println("output directory: " + outDir);

        SourceFiles sourceFiles = SourceFiles.collect(inputs);
        String specification = readSpecification(property);

        List<ValueMarker> values = new ArrayList<>();
        TargetMarker target = null;
        if (!markers.trim().isEmpty()) {
            String decoded = new String(Base64.getDecoder().decode(markers.trim()), StandardCharsets.UTF_8);
            for (String line : decoded.split("\n")) {
                int idx = line.indexOf("[WITNESS_TARGET]");
                if (idx >= 0) {
                    target = TargetMarker.parse(decodePayload(line.substring(idx + "[WITNESS_TARGET]".length())));
                    continue;
                }
                idx = line.indexOf("[WITNESS]");
                if (idx >= 0) {
                    values.add(ValueMarker.parse(decodePayload(line.substring(idx + "[WITNESS]".length()))));
                }
            }
        }
        if (values.isEmpty()) {
            System.out.println("No witness values recorded, assuming default violation");
        }
        if (target == null) {
            System.out.println("No witness target recorded, the witness has no target waypoint");
        }

        App app = new App(sourceFiles, outDir);
        app.saveYamlWitness(values, target, specification, producerVersion);
        app.saveGraphmlWitness(values);
    }

    private static String decodePayload(String base64) {
        return new String(Base64.getDecoder().decode(base64.trim()), StandardCharsets.UTF_8);
    }

    private static String readSpecification(String property) {
        if (property == null) {
            System.out.println("No property file given, assuming specification: " + DEFAULT_SPECIFICATION);
            return DEFAULT_SPECIFICATION;
        }
        try {
            String spec = Files.readString(Paths.get(property), StandardCharsets.UTF_8).trim();
            if (!spec.isEmpty()) {
                return spec;
            }
        } catch (IOException e) {
            System.out.println("Could not read property file " + property + ": " + e.getMessage());
        }
        System.out.println("Assuming specification: " + DEFAULT_SPECIFICATION);
        return DEFAULT_SPECIFICATION;
    }

    // ------------------------------------------------------------------
    // YAML witness (format 2.3)
    // ------------------------------------------------------------------

    private void saveYamlWitness(
            List<ValueMarker> values, TargetMarker target, String specification, String producerVersion)
            throws IOException {
        YamlWitness witness = new YamlWitness(PRODUCER, producerVersion, specification, sourceFiles);

        for (ValueMarker value : values) {
            Optional<InputFile> file = sourceFiles.resolve(value.getClassName(), value.getSourceFile());
            String fileName;
            Integer column = null;
            if (file.isPresent()) {
                fileName = file.get().getDisplayPath();
                String loc = file.get().getLine(value.getLine());
                int col = loc == null ? -1 : nondetCallColumn(loc, value.getCallIndex());
                if (col > 0) {
                    column = col;
                } else {
                    System.out.println(
                            "Could not locate nondet call " + value.getCallIndex() + " in " + fileName
                                    + ":" + value.getLine() + " (" + loc + ")");
                }
            } else {
                fileName = fallbackFileName(value.getClassName(), value.getSourceFile());
                System.out.println("Could not find the source of " + value.getClassName() + ", using " + fileName);
            }
            String constraint = JavaLiterals.resultConstraint(value.getValue(), value.getTypeDesc());
            witness.add(Waypoint.functionReturn(constraint, fileName, value.getLine(), column));
        }

        if (target != null) {
            Optional<Waypoint> targetWaypoint = targetWaypoint(target);
            if (targetWaypoint.isPresent()) {
                witness.add(targetWaypoint.get());
            } else {
                System.out.println("No stack frame of " + target.getThrowableClass()
                        + " lies in the task sources: " + target.getFrames());
            }
        }

        for (Waypoint wp : witness.getWaypoints()) {
            System.out.println("Waypoint: " + wp);
        }
        Path file = outDir.resolve("witness.yml");
        System.out.println("Writing violation witness to file: " + file);
        Files.writeString(file, witness.render(), StandardCharsets.UTF_8);
    }

    /** The innermost stack frame inside the task sources becomes the target. */
    private Optional<Waypoint> targetWaypoint(TargetMarker target) {
        for (TargetMarker.Frame frame : target.getFrames()) {
            if (frame.getLine() < 1) {
                continue;
            }
            Optional<InputFile> file = sourceFiles.resolve(frame.getClassName(), frame.getFileName());
            if (file.isEmpty()) {
                continue;
            }
            String loc = file.get().getLine(frame.getLine());
            if (loc == null) {
                System.out.println("Frame " + frame + " is outside of " + file.get().getPath());
                continue;
            }
            int col = statementColumn(loc, target.isAssertionError());
            return Optional.of(
                    Waypoint.target(file.get().getDisplayPath(), frame.getLine(), col > 0 ? col : null));
        }
        return Optional.empty();
    }

    /**
     * The 1-based column of the closing parenthesis of the {@code callIndex}-th nondet call in the
     * line, -1 if there is none.
     */
    static int nondetCallColumn(String line, int callIndex) {
        Matcher m = NONDET_CALL.matcher(line);
        int found = 0;
        while (m.find()) {
            if (found++ < callIndex) {
                continue;
            }
            int open = m.end() - 1;
            int depth = 0;
            for (int i = open; i < line.length(); i++) {
                char c = line.charAt(i);
                if (c == '(') {
                    depth++;
                } else if (c == ')') {
                    depth--;
                    if (depth == 0) {
                        return i + 1;
                    }
                }
            }
            return -1;
        }
        return -1;
    }

    /**
     * The 1-based column of the first character of the violating statement on the line: the
     * {@code assert} of a failed assertion, the {@code throw} of an explicit throw, otherwise the
     * first token that is not a closing brace or an {@code else}.
     */
    static int statementColumn(String line, boolean assertion) {
        if (assertion) {
            Matcher m = ASSERT_KEYWORD.matcher(line);
            if (m.find()) {
                return m.start() + 1;
            }
        }
        Matcher t = THROW_KEYWORD.matcher(line);
        if (t.find()) {
            return t.start() + 1;
        }
        int i = skipWhitespace(line, 0);
        while (i < line.length()) {
            if (line.charAt(i) == '}' || line.charAt(i) == '{') {
                i = skipWhitespace(line, i + 1);
            } else if (line.startsWith("else", i)
                    && (i + 4 == line.length() || !Character.isJavaIdentifierPart(line.charAt(i + 4)))) {
                i = skipWhitespace(line, i + 4);
            } else {
                break;
            }
        }
        return i < line.length() ? i + 1 : -1;
    }

    private static int skipWhitespace(String line, int i) {
        while (i < line.length() && Character.isWhitespace(line.charAt(i))) {
            i++;
        }
        return i;
    }

    private static String fallbackFileName(String className, String sourceFile) {
        String internal = className.replace('.', '/');
        int slash = internal.lastIndexOf('/');
        String pkgDir = slash < 0 ? "" : internal.substring(0, slash + 1);
        if (sourceFile != null && !sourceFile.isEmpty()) {
            return pkgDir + sourceFile;
        }
        String simple = internal.substring(slash + 1);
        int dollar = simple.indexOf('$');
        return pkgDir + (dollar < 0 ? simple : simple.substring(0, dollar)) + ".java";
    }

    // ------------------------------------------------------------------
    // GraphML witness (legacy format, kept for the GraphML-based validators)
    // ------------------------------------------------------------------

    private void saveGraphmlWitness(List<ValueMarker> values) {
        STGroup group = new STRawGroupDir(templateDir(), '$', '$');
        ST st;
        if (values.isEmpty()) {
            st = group.getInstanceOf("default_violation");
        } else {
            List<WitnessNode> nodes = new ArrayList<>();
            List<WitnessEdge> edges = new ArrayList<>();

            int nodeId = 0;
            WitnessNode initNode = new WitnessNode(nodeId++);
            nodes.add(initNode);
            initNode.addData("entry", "true");
            WitnessNode curNode = initNode;

            for (ValueMarker value : values) {
                Optional<InputFile> file = sourceFiles.resolve(value.getClassName(), value.getSourceFile());
                String clazz = file.map(InputFile::getRelativePath)
                        .orElse(fallbackFileName(value.getClassName(), value.getSourceFile()));
                String loc = file.map(f -> f.getLine(value.getLine())).orElse(null);
                // Escape XML special characters in scope to avoid XML parse errors
                // (e.g., <init> contains angle brackets that break XML parsing)
                String scope = "L" + value.getClassName() + ";." + value.getMethodDesc();
                scope = scope.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
                WitnessAssumption wa = new WitnessAssumption(value.getValue(), clazz, scope, value.getLine());
                String assumption = computeAssumption(loc, wa, value.isString());

                WitnessNode prevNode = curNode;
                curNode = new WitnessNode(nodeId++);
                nodes.add(curNode);
                edges.add(new WitnessEdge(prevNode, wa, assumption, curNode));
            }
            curNode.addData("violation", "true");

            st = group.getInstanceOf("witness");
            st.add("nodes", nodes);
            st.add("edges", edges);
        }
        Path file = outDir.resolve("witness.graphml");
        try {
            System.out.println("Writing violation witness to file: " + file);
            Files.writeString(file, st.render(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            System.out.println("Error writing witness to file: " + e.getMessage());
        }
    }

    /** The {@code witnesses} template directory next to the jar, or relative to the cwd. */
    private static String templateDir() {
        if (Files.isDirectory(Paths.get("witnesses"))) {
            return "witnesses";
        }
        try {
            Path jar = Paths.get(App.class.getProtectionDomain().getCodeSource().getLocation().toURI());
            for (Path dir = jar.getParent(); dir != null; dir = dir.getParent()) {
                Path candidate = dir.resolve("witnesses");
                if (Files.isDirectory(candidate)) {
                    return candidate.toString();
                }
            }
        } catch (URISyntaxException | RuntimeException e) {
            // fall through
        }
        return "witnesses";
    }

    private String computeAssumption(String lineOfCode, WitnessAssumption wa, boolean knownString) {
        if (lineOfCode == null) {
            return "true";
        }

        // Check if this is a string type by looking for nondetString() in the line
        boolean isStringType = knownString || lineOfCode.contains("nondetString()");

        int idx = lineOfCode.indexOf("Verifier");
        if (idx < 0) {
            return "true";
        }
        lineOfCode = lineOfCode.substring(0, idx).trim();
        idx = lineOfCode.lastIndexOf("=");
        if (idx < 0) {
            // No assignment found - this is likely a return statement or direct call
            // Use the witness value directly (e.g., "true", "false", or a literal value)
            return wa.getValue();
        }
        // Check if this is a comparison (==) not an assignment (=)
        // If the character before '=' is also '=', this is a comparison, not an assignment
        if (idx > 0 && lineOfCode.charAt(idx - 1) == '=') {
            // This is a comparison like "if (pos == ..." - no variable assignment
            return wa.getValue();
        }
        lineOfCode = lineOfCode.substring(0, idx).trim();
        String[] parts = lineOfCode.split(" ");
        String id = parts[parts.length - 1].trim();

        // For string types, always use .equals() format with properly quoted value
        if (isStringType) {
            String value = wa.getValue();
            // Add quotes around the value if not already present
            if (!value.startsWith("\"")) {
                // Escape any quotes and backslashes within the string value
                value = value.replace("\\", "\\\\").replace("\"", "\\\"");
                value = "\"" + value + "\"";
            }
            return id + ".equals(" + value + ")";
        }

        // For primitive types, use assignment format
        return id + " = " + wa.getValue();
    }
}
