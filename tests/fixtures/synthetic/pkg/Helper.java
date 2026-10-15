package pkg;

import org.sosy_lab.sv_benchmarks.Verifier;

public class Helper {
  public static boolean check(int x) {
    return x > Verifier.nondetInt();
  }
}
