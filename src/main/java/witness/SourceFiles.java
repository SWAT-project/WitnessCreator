package witness;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Stream;

/**
 * The Java source files of the verification task, as they were given to the verifier (files or
 * directories). Resolves classes to their source files and provides line contents and hashes.
 */
public final class SourceFiles {

    /** One input file of the task. */
    public static final class InputFile {
        private final String displayPath;
        private final Path path;
        private final String relativePath;
        private List<String> lines;
        private String sha256;

        InputFile(String displayPath, Path path, String relativePath) {
            this.displayPath = displayPath;
            this.path = path;
            this.relativePath = relativePath;
        }

        /** The path as it is written into the witness (input as given + relative path). */
        public String getDisplayPath() {
            return displayPath;
        }

        public Path getPath() {
            return path;
        }

        /** Path relative to the input root it was found in, '/'-separated. */
        public String getRelativePath() {
            return relativePath;
        }

        public String getFileName() {
            return path.getFileName().toString();
        }

        public List<String> getLines() {
            if (lines == null) {
                try {
                    lines = Files.readAllLines(path, StandardCharsets.UTF_8);
                } catch (IOException e) {
                    System.out.println("Could not read " + path + ": " + e.getMessage());
                    lines = Collections.emptyList();
                }
            }
            return lines;
        }

        /** The 1-based line, or {@code null} if the file does not have it. */
        public String getLine(int lineNumber) {
            List<String> l = getLines();
            if (lineNumber < 1 || lineNumber > l.size()) {
                return null;
            }
            return l.get(lineNumber - 1);
        }

        public String getSha256() throws IOException {
            if (sha256 == null) {
                try {
                    MessageDigest digest = MessageDigest.getInstance("SHA-256");
                    byte[] hash = digest.digest(Files.readAllBytes(path));
                    StringBuilder sb = new StringBuilder();
                    for (byte b : hash) {
                        sb.append(String.format("%02x", b));
                    }
                    sha256 = sb.toString();
                } catch (NoSuchAlgorithmException e) {
                    throw new IllegalStateException(e);
                }
            }
            return sha256;
        }
    }

    private final List<InputFile> files;

    private SourceFiles(List<InputFile> files) {
        this.files = Collections.unmodifiableList(files);
    }

    /**
     * Collects all {@code .java} files of the given inputs. Directories are searched recursively,
     * the files are ordered by path inside each input.
     */
    public static SourceFiles collect(List<String> inputs) {
        List<InputFile> files = new ArrayList<>();
        Set<Path> seen = new HashSet<>(); // a file reachable through several inputs is listed once
        for (String input : inputs) {
            Path root = Paths.get(input);
            if (Files.isDirectory(root)) {
                String prefix = stripTrailingSlash(input);
                try (Stream<Path> walk = Files.walk(root)) {
                    List<Path> javaFiles =
                            walk.filter(Files::isRegularFile)
                                    .filter(p -> p.getFileName().toString().endsWith(".java"))
                                    .sorted()
                                    .toList();
                    for (Path p : javaFiles) {
                        if (seen.add(p.toAbsolutePath().normalize())) {
                            String rel = toSlashes(root.relativize(p).toString());
                            files.add(new InputFile(prefix + "/" + rel, p, rel));
                        }
                    }
                } catch (IOException e) {
                    System.out.println("Could not read input directory " + input + ": " + e.getMessage());
                }
            } else if (Files.isRegularFile(root)) {
                if (root.getFileName().toString().endsWith(".java")
                        && seen.add(root.toAbsolutePath().normalize())) {
                    files.add(new InputFile(toSlashes(input), root, root.getFileName().toString()));
                }
            } else {
                System.out.println("Ignoring missing input: " + input);
            }
        }
        return new SourceFiles(files);
    }

    public List<InputFile> getFiles() {
        return files;
    }

    public boolean isEmpty() {
        return files.isEmpty();
    }

    /**
     * Finds the source file of a class.
     *
     * @param className JVM internal ({@code pkg/Outer$Inner}) or dotted ({@code pkg.Outer$Inner})
     *     class name
     * @param sourceFileName the class' SourceFile attribute, may be empty or {@code null}
     */
    public Optional<InputFile> resolve(String className, String sourceFileName) {
        String internal = className.replace('.', '/');
        int slash = internal.lastIndexOf('/');
        String pkgDir = slash < 0 ? "" : internal.substring(0, slash);
        String simple = slash < 0 ? internal : internal.substring(slash + 1);
        int dollar = simple.indexOf('$');
        String outer = dollar < 0 ? simple : simple.substring(0, dollar);

        List<String> fileNames = new ArrayList<>();
        if (sourceFileName != null && !sourceFileName.isEmpty()) {
            fileNames.add(sourceFileName);
        }
        fileNames.add(outer + ".java");

        // Exact package path first, then any path ending with the package path, then by name only
        for (String fileName : fileNames) {
            String rel = pkgDir.isEmpty() ? fileName : pkgDir + "/" + fileName;
            Optional<InputFile> match = find(f -> f.getRelativePath().equals(rel));
            if (match.isEmpty()) {
                match = find(f -> f.getRelativePath().endsWith("/" + rel));
            }
            if (match.isPresent()) {
                return match;
            }
        }
        for (String fileName : fileNames) {
            Optional<InputFile> match = find(f -> f.getFileName().equals(fileName));
            if (match.isPresent()) {
                return match;
            }
        }
        return Optional.empty();
    }

    private Optional<InputFile> find(java.util.function.Predicate<InputFile> predicate) {
        return files.stream().filter(predicate).findFirst();
    }

    private static String stripTrailingSlash(String s) {
        String r = toSlashes(s);
        while (r.length() > 1 && r.endsWith("/")) {
            r = r.substring(0, r.length() - 1);
        }
        return r;
    }

    private static String toSlashes(String s) {
        return s.replace('\\', '/');
    }
}
