import pytest

from witnesscreator.columns import mask_non_code, nondet_call_column, statement_column
from witnesscreator.sources import SourceFiles, fallback_file_name, split_lines


def test_column_of_closing_parenthesis():
    line = "    Boolean input_1_0 = Verifier.nondetBoolean();"
    assert nondet_call_column(line, 0) == 48
    assert nondet_call_column(line, 1) is None
    two = "    if (!chunked && Verifier.nondetInt() > 0 && Verifier.nondetInt() != 0) {"
    c0, c1 = nondet_call_column(two, 0), nondet_call_column(two, 1)
    assert two[c0 - 1] == ")" and two[c1 - 1] == ")" and c0 < c1
    assert nondet_call_column("x = Verifier.nondetInt ( );", 0) == 26
    assert nondet_call_column("no call here", 0) is None
    assert nondet_call_column("Verifier.nondetInt(", 0) is None
    assert nondet_call_column("x = nondetInt(f(1, (2)));", 0) == 24
    assert nondet_call_column("", 0) is None
    assert nondet_call_column(None, 0) is None
    assert nondet_call_column("Verifier.nondetInt()", -1) is None


def test_nondet_call_needs_word_boundary():
    assert nondet_call_column("x = mynondetInt();", 0) is None
    assert nondet_call_column("x = my_nondetInt();", 0) is None
    assert nondet_call_column("x = Verifier.nondetInt();", 0) == 24
    assert nondet_call_column("x = nondet();", 0) == 12


def test_calls_in_comments_and_strings_are_ignored():
    line = mask_non_code('String s = "nondetInt()"; int x = Verifier.nondetInt(); // nondetInt()')
    assert nondet_call_column(line, 0) == 54
    assert nondet_call_column(line, 1) is None
    line = mask_non_code('int x = Verifier.nondetInt(/* ) */);')
    assert nondet_call_column(line, 0) == 35
    line = mask_non_code("char c = ')'; int x = Verifier.nondetInt();")
    assert nondet_call_column(line, 0) == 42


def test_mask_non_code_keeps_positions():
    src = 'a = "x\\"y"; // c\nb = \'"\'; /* multi\nline */ c = 1;\nd = """t\nb""" + 2;\n'
    masked = mask_non_code(src)
    assert len(masked) == len(src)
    assert masked.count("\n") == src.count("\n")
    assert masked.splitlines() == ["a =       ;     ", "b =    ;         ", "        c = 1;", "d =     ", "     + 2;"]
    # unterminated constructs do not raise
    assert len(mask_non_code('x = "unterminated')) == len('x = "unterminated')
    assert len(mask_non_code("/* never closed")) == len("/* never closed")
    assert mask_non_code("") == ""


def test_column_of_violating_statement():
    assert statement_column("    } else assert false;", True) == 12
    assert statement_column("    assert !(output_1 == 1);", True) == 5
    assert statement_column("    assert !(output_1 == 1);", False) == 5
    assert statement_column("    } throw new RuntimeException();", False) == 7
    assert statement_column("    int x = a / b;", False) == 5
    assert statement_column("    } else { int x = a / b; }", False) == 14
    assert statement_column("\t\t\tx = elsewhere / 0;", False) == 4  # a tab is one column
    assert statement_column("    }", False) is None
    assert statement_column("", False) is None
    assert statement_column(None, False) is None
    assert statement_column("    elsewhere = 1;", False) == 5
    assert statement_column("  x.throws();", False) == 3
    assert statement_column("  if (b) throw new Error();", True) == 10
    # the keyword inside a string or comment does not count once masked
    assert statement_column(mask_non_code('  s = "assert"; assert x;'), True) == 17
    assert statement_column(mask_non_code("  } // assert here"), True) is None


def test_split_lines_only_on_line_breaks():
    assert split_lines("a\nb\r\nc\rd") == ["a", "b", "c", "d"]
    assert split_lines("a\n") == ["a"]
    assert split_lines("") == []
    assert split_lines("a\x0cb c\n") == ["a\x0cb c"]


@pytest.fixture
def tree(tmp_path):
    task = tmp_path / "task"
    (task / "pkg").mkdir(parents=True)
    (task / "Main.java").write_text("class Main {}\nclass Helper {}\n")
    (task / "pkg" / "Foo.java").write_text("package pkg;\nclass Foo {}\n")
    (task / "notes.txt").write_text("ignored")
    common = tmp_path / "common"
    (common / "org" / "sosy_lab" / "sv_benchmarks").mkdir(parents=True)
    (common / "org" / "sosy_lab" / "sv_benchmarks" / "Verifier.java").write_text("package org.sosy_lab.sv_benchmarks;\n")
    return tmp_path, task, common


def test_collect_lists_inputs_as_given(tree):
    tmp, task, common = tree
    files = SourceFiles.collect([str(common) + "/", str(task)])
    assert [f.display_path for f in files] == [
        f"{common}/org/sosy_lab/sv_benchmarks/Verifier.java",
        f"{task}/Main.java",
        f"{task}/pkg/Foo.java",
    ]
    assert [f.relative_path for f in files] == ["org/sosy_lab/sv_benchmarks/Verifier.java", "Main.java", "pkg/Foo.java"]
    assert len(files.files[0].sha256) == 64
    # a file reachable through several inputs is listed once
    nested = SourceFiles.collect([str(task / "pkg"), str(task), str(task / "pkg" / "Foo.java")])
    assert [f.display_path for f in nested] == [f"{task}/pkg/Foo.java", f"{task}/Main.java"]
    # relative inputs are resolved against base_dir but displayed as given
    rel = SourceFiles.collect(["../common/", "Main.java"], base_dir=task)
    assert [f.display_path for f in rel] == ["../common/org/sosy_lab/sv_benchmarks/Verifier.java", "Main.java"]
    assert rel.files[1].path.exists()
    # missing and non-java inputs are ignored
    assert len(SourceFiles.collect([str(tmp / "missing"), str(task / "notes.txt"), ""])) == 0
    assert len(SourceFiles.collect([str(task / "notes.txt")])) == 0


def test_resolve_classes(tree):
    _, task, common = tree
    files = SourceFiles.collect([str(common), str(task)])
    assert files.resolve("Main", "Main.java").relative_path == "Main.java"
    assert files.resolve("Main$1", None).relative_path == "Main.java"
    assert files.resolve("Helper", "Main.java").relative_path == "Main.java"
    assert files.resolve("pkg/Foo", "Foo.java").relative_path == "pkg/Foo.java"
    assert files.resolve("pkg.Foo$Inner", "").relative_path == "pkg/Foo.java"
    assert files.resolve("org.sosy_lab.sv_benchmarks.Verifier", "Verifier.java").relative_path == "org/sosy_lab/sv_benchmarks/Verifier.java"
    assert files.resolve("Missing", "") is None
    # a file whose package declaration contradicts the class is never taken
    assert files.resolve("other.Foo", "Foo.java", allow_name_only=True) is None
    assert files.resolve("other.Main", None, allow_name_only=True) is None
    assert files.resolve("Foo", None, allow_name_only=True) is None  # Foo lives in pkg/
    # a file without a readable package declaration only resolves by name when allowed
    (task / "Empty.java").write_text("")
    files = SourceFiles.collect([str(common), str(task)])
    assert files.resolve("some.pkg.Empty", None, allow_name_only=True).relative_path == "Empty.java"
    assert files.resolve("some.pkg.Empty", None, allow_name_only=False) is None
    # a matching declaration is accepted whatever the path (e.g. sources below an src/ dir)
    (task / "src").mkdir()
    (task / "src" / "Bar.java").write_text("/* c */ package pkg; class Bar {}\n")
    files = SourceFiles.collect([str(task)])
    assert files.resolve("pkg.Bar", "Bar.java", allow_name_only=False).relative_path == "src/Bar.java"
    assert files.resolve("Bar", "Bar.java", allow_name_only=True) is None
    # the package path may be a suffix of the file's path (input root above the package root)
    outer = SourceFiles.collect([str(task.parent)])
    assert outer.resolve("pkg.Foo", "Foo.java", allow_name_only=False).relative_path == "task/pkg/Foo.java"
    assert outer.resolve("Main", "Main.java", allow_name_only=False).relative_path == "task/Main.java"


def test_resolve_file_name(tree):
    _, task, common = tree
    files = SourceFiles.collect([str(common), str(task)])
    assert files.resolve_file_name(f"{task}/pkg/Foo.java").relative_path == "pkg/Foo.java"
    assert files.resolve_file_name("pkg/Foo.java").relative_path == "pkg/Foo.java"
    assert files.resolve_file_name("./Foo.java").relative_path == "pkg/Foo.java"
    assert files.resolve_file_name("Verifier.java").relative_path == "org/sosy_lab/sv_benchmarks/Verifier.java"
    assert files.resolve_file_name("Nope.java") is None
    assert files.resolve_file_name("") is None


def test_lines_and_masking(tree):
    _, task, _ = tree
    files = SourceFiles.collect([str(task)])
    main = files.resolve("Main", None)
    assert main.line(1) == "class Main {}"
    assert main.line(2) == "class Helper {}"
    assert main.line(3) is None
    assert main.line(0) is None
    assert main.masked_line(1) == "class Main {}"
    assert main.masked_line(9) is None
    assert main.package == ""
    assert files.resolve("pkg.Foo", None).package == "pkg"


def test_fallback_file_name():
    assert fallback_file_name("pkg.Main$1", "Main.java") == "pkg/Main.java"
    assert fallback_file_name("pkg/Main$1", None) == "pkg/Main.java"
    assert fallback_file_name("Main", "") == "Main.java"
    assert fallback_file_name("a.b.Outer$Inner$2", None) == "a/b/Outer.java"
