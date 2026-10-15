import org.sosy_lab.sv_benchmarks.Verifier;
import pkg.Helper;

public class Main {
  static class Inner {
    int pick() {
      // Verifier.nondetInt() in a comment
      String s = "Verifier.nondetInt()"; // and in a string literal
      return Verifier.nondetInt() + Verifier.nondetInt(); // two calls, one line
    }
  }

  public static void main(String[] args) {
    char c = Verifier.nondetChar();
    double d = Verifier.nondetDouble();
    float f = Verifier.nondetFloat();
    long l = Verifier.nondetLong();
    String s = Verifier.nondetString();
    int sum = new Inner().pick();
    if (Helper.check(sum) && Companion.flag() && s.length() > 0) {
      throw new IllegalStateException("boom");
    }
    assert false;
  }
}

class Companion {
  static boolean flag() {
    return Verifier.nondetBoolean();
  }
}
