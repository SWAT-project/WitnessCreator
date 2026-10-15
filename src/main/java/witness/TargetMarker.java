package witness;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * A decoded {@code [WITNESS_TARGET]} marker: the uncaught throwable that ended the violating run
 * together with its stack trace (innermost frame first).
 *
 * <p>Payload format: {@code throwableClass@@@className@@fileName@@line;className@@fileName@@line;...}
 */
public final class TargetMarker {
    private final String throwableClass;
    private final List<Frame> frames;

    public static final class Frame {
        private final String className;
        private final String fileName;
        private final int line;

        Frame(String className, String fileName, int line) {
            this.className = className;
            this.fileName = fileName;
            this.line = line;
        }

        /** Fully qualified (dotted) class name. */
        public String getClassName() {
            return className;
        }

        /** Source file name from the stack trace, empty if unknown. */
        public String getFileName() {
            return fileName;
        }

        public int getLine() {
            return line;
        }

        @Override
        public String toString() {
            return className + "(" + fileName + ":" + line + ")";
        }
    }

    private TargetMarker(String throwableClass, List<Frame> frames) {
        this.throwableClass = throwableClass;
        this.frames = Collections.unmodifiableList(frames);
    }

    public static TargetMarker parse(String payload) {
        int idx = payload.indexOf("@@@");
        if (idx < 0) {
            throw new IllegalArgumentException("Invalid witness target marker: " + payload);
        }
        String throwableClass = payload.substring(0, idx).trim();
        List<Frame> frames = new ArrayList<>();
        String rest = payload.substring(idx + 3).trim();
        if (!rest.isEmpty()) {
            for (String frame : rest.split(";")) {
                String[] parts = frame.split("@@", -1);
                if (parts.length != 3) {
                    continue;
                }
                int line;
                try {
                    line = Integer.parseInt(parts[2].trim());
                } catch (NumberFormatException e) {
                    line = -1;
                }
                frames.add(new Frame(parts[0].trim(), parts[1].trim(), line));
            }
        }
        return new TargetMarker(throwableClass, frames);
    }

    public String getThrowableClass() {
        return throwableClass;
    }

    public boolean isAssertionError() {
        return "java.lang.AssertionError".equals(throwableClass);
    }

    public List<Frame> getFrames() {
        return frames;
    }
}
