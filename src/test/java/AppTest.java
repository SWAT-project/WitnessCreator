import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import witness.SourceFiles;

class AppTest {

    @Test
    void columnOfClosingParenthesis() {
        String line = "    Boolean input_1_0 = Verifier.nondetBoolean();";
        assertEquals(48, App.nondetCallColumn(line, 0));
        assertEquals(-1, App.nondetCallColumn(line, 1));

        String two = "    if (!chunked && Verifier.nondetInt() > 0 && Verifier.nondetInt() != 0) {";
        assertEquals(')', two.charAt(App.nondetCallColumn(two, 0) - 1));
        assertEquals(')', two.charAt(App.nondetCallColumn(two, 1) - 1));
        assertTrue(App.nondetCallColumn(two, 0) < App.nondetCallColumn(two, 1));

        String spaced = "x = Verifier.nondetInt ( );";
        assertEquals(26, App.nondetCallColumn(spaced, 0));
        assertEquals(-1, App.nondetCallColumn("no call here", 0));
        assertEquals(-1, App.nondetCallColumn("Verifier.nondetInt(", 0));
    }

    @Test
    void columnOfViolatingStatement() {
        assertEquals(12, App.statementColumn("    } else assert false;", true));
        assertEquals(5, App.statementColumn("    assert !(output_1 == 1);", true));
        assertEquals(5, App.statementColumn("    assert !(output_1 == 1);", false));
        assertEquals(7, App.statementColumn("    } throw new RuntimeException();", false));
        assertEquals(5, App.statementColumn("    int x = a / b;", false));
        assertEquals(14, App.statementColumn("    } else { int x = a / b; }", false));
        // tabs count as one character, like any other
        assertEquals(4, App.statementColumn("\t\t\tx = elsewhere / 0;", false));
        assertEquals(-1, App.statementColumn("    }", false));
        assertEquals(-1, App.statementColumn("", false));
    }

    @Test
    void resolvesSources(@TempDir Path dir) throws IOException {
        Path task = dir.resolve("task");
        Files.createDirectories(task.resolve("pkg"));
        Files.writeString(task.resolve("Main.java"), "class Main {}\nclass Helper {}\n");
        Files.writeString(task.resolve("pkg/Foo.java"), "package pkg;\nclass Foo {}\n");
        Path common = dir.resolve("common");
        Files.createDirectories(common.resolve("org/sosy_lab/sv_benchmarks"));
        Files.writeString(common.resolve("org/sosy_lab/sv_benchmarks/Verifier.java"), "package org.sosy_lab.sv_benchmarks;\n");

        SourceFiles files = SourceFiles.collect(List.of(common + "/", task.toString()));
        assertEquals(
                List.of(
                        common + "/org/sosy_lab/sv_benchmarks/Verifier.java",
                        task + "/Main.java",
                        task + "/pkg/Foo.java"),
                files.getFiles().stream().map(SourceFiles.InputFile::getDisplayPath).toList());

        assertEquals("Main.java", files.resolve("Main", "Main.java").get().getRelativePath());
        assertEquals("Main.java", files.resolve("Main$1", "").get().getRelativePath());
        assertEquals("Main.java", files.resolve("Helper", "Main.java").get().getRelativePath());
        assertEquals("pkg/Foo.java", files.resolve("pkg/Foo", "Foo.java").get().getRelativePath());
        assertEquals("pkg/Foo.java", files.resolve("pkg.Foo$Inner", "").get().getRelativePath());
        assertEquals(
                "org/sosy_lab/sv_benchmarks/Verifier.java",
                files.resolve("org.sosy_lab.sv_benchmarks.Verifier", "Verifier.java").get().getRelativePath());
        assertEquals(Optional.empty(), files.resolve("Missing", ""));
        assertEquals(64, files.getFiles().get(0).getSha256().length());

        // A file reachable through several inputs (e.g. a nested common/ dir) is listed once
        SourceFiles nested = SourceFiles.collect(List.of(task + "/pkg", task.toString(), task + "/pkg/Foo.java"));
        assertEquals(
                List.of(task + "/pkg/Foo.java", task + "/Main.java"),
                nested.getFiles().stream().map(SourceFiles.InputFile::getDisplayPath).toList());
    }

    @Test
    void writesYamlAndGraphmlWitness(@TempDir Path dir) throws IOException {
        Path task = dir.resolve("task");
        Files.createDirectories(task);
        Files.writeString(
                task.resolve("Main.java"),
                String.join(
                        "\n",
                        "import org.sosy_lab.sv_benchmarks.Verifier;",
                        "public class Main {",
                        "  public static void main(String[] args) {",
                        "    int x = Verifier.nondetInt();",
                        "    String s = Verifier.nondetString();",
                        "    if (x == 3 && s.equals(\"a\\\"b\")) {",
                        "      assert false;",
                        "    }",
                        "  }",
                        "}",
                        ""));
        Path prp = dir.resolve("valid-assert.prp");
        Files.writeString(prp, "CHECK( init(Main.main()), LTL(G assert) )\n");
        Path out = dir.resolve("out");

        String markers =
                marker("[WITNESS]", "3@@@4@@@Main@@@main([Ljava/lang/String;)V@@@0@@@I@@@Main.java")
                        + "\n"
                        + marker("[WITNESS]", "a\"b@@@5@@@Main@@@main([Ljava/lang/String;)V@@@0@@@Ljava/lang/String;@@@Main.java")
                        + "\n"
                        + marker("[WITNESS_TARGET]", "java.lang.AssertionError@@@Main@@Main.java@@7");
        App.main(new String[] {
            Base64.getEncoder().encodeToString(markers.getBytes(StandardCharsets.UTF_8)),
            "--input", task.toString(),
            "--property", prp.toString(),
            "--out", out.toString(),
            "--producer-version", "test"
        });

        String yaml = Files.readString(out.resolve("witness.yml"));
        assertTrue(yaml.startsWith("- entry_type: \"violation_sequence\"\n"));
        assertTrue(yaml.contains("    format_version: \"2.3\"\n"));
        assertTrue(yaml.contains("      name: \"SWAT\"\n      version: \"test\"\n"));
        assertTrue(yaml.contains("      - \"" + task + "/Main.java\"\n"));
        assertTrue(yaml.contains("      specification: \"CHECK( init(Main.main()), LTL(G assert) )\"\n"));
        assertTrue(yaml.contains("      language: \"Java\"\n"));
        assertFalse(yaml.contains("data_model"));
        assertTrue(yaml.contains("          value: \"\\\\result == 3\"\n          format: \"java_expression\"\n"));
        assertTrue(yaml.contains("          line: 4\n          column: 32\n"));
        assertTrue(yaml.contains("          value: \"\\\\result.equals(\\\"a\\\\\\\"b\\\")\"\n"));
        assertTrue(yaml.contains("          line: 5\n          column: 38\n"));
        assertTrue(yaml.contains("        type: \"target\"\n        action: \"follow\"\n        location:\n"));
        assertTrue(yaml.contains("          line: 7\n          column: 7\n"));
        assertEquals(3, yaml.split("  - segment:\n").length - 1);

        String graphml = Files.readString(out.resolve("witness.graphml"));
        assertTrue(graphml.contains("<data key=\"assumption\">x = 3</data>"));
        assertTrue(graphml.contains("<data key=\"assumption\">s.equals(\"a\\\"b\")</data>"));
        assertTrue(graphml.contains("<data key=\"violation\">true</data>"));
    }

    @Test
    void defaultViolationWithoutMarkers(@TempDir Path dir) throws IOException {
        Path task = dir.resolve("task");
        Files.createDirectories(task);
        Files.writeString(task.resolve("Main.java"), "public class Main {\n  public static void main(String[] a) {\n    assert false;\n  }\n}\n");
        Path out = dir.resolve("out");

        App.main(new String[] {"", "--input", task.toString(), "--out", out.toString()});
        String yaml = Files.readString(out.resolve("witness.yml"));
        assertTrue(yaml.contains("  content: []\n"));
        assertTrue(Files.readString(out.resolve("witness.graphml")).contains("<data key=\"violation\">true</data>"));

        // A target alone is enough for a final segment
        App.main(new String[] {
            Base64.getEncoder().encodeToString(
                    marker("[WITNESS_TARGET]", "java.lang.AssertionError@@@Main@@Main.java@@3").getBytes()),
            "--input", task.toString(), "--out", out.toString()
        });
        yaml = Files.readString(out.resolve("witness.yml"));
        assertTrue(yaml.contains("        type: \"target\"\n"));
        assertTrue(yaml.contains("          line: 3\n          column: 5\n"));
    }

    @Test
    void legacyInvocationStillWorks(@TempDir Path dir) throws IOException {
        Files.writeString(dir.resolve("Main.java"), "class Main {\n  int x = Verifier.nondetInt();\n}\n");
        String markers = marker("[WITNESS]", "1@@@2@@@Main@@@<init>()V");
        App.main(new String[] {Base64.getEncoder().encodeToString(markers.getBytes()), dir.toString()});
        String yaml = Files.readString(dir.resolve("witness.yml"));
        assertTrue(yaml.contains("          value: \"\\\\result == 1\"\n"));
        assertTrue(yaml.contains("          line: 2\n          column: 30\n"));
        assertTrue(Files.readString(dir.resolve("witness.graphml")).contains("&lt;init&gt;"));
    }

    private static String marker(String kind, String payload) {
        return "prefix " + kind + " " + Base64.getEncoder().encodeToString(payload.getBytes(StandardCharsets.UTF_8));
    }
}
