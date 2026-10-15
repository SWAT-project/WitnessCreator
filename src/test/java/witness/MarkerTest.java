package witness;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class MarkerTest {

    @Test
    void parsesCurrentFormat() {
        ValueMarker m = ValueMarker.parse("5@@@13@@@pkg/Main$1@@@main([Ljava/lang/String;)V@@@2@@@I@@@Main.java");
        assertEquals("5", m.getValue());
        assertEquals(13, m.getLine());
        assertEquals("pkg/Main$1", m.getClassName());
        assertEquals("main([Ljava/lang/String;)V", m.getMethodDesc());
        assertEquals(2, m.getCallIndex());
        assertEquals("I", m.getTypeDesc());
        assertEquals("Main.java", m.getSourceFile());
    }

    @Test
    void stringValuesMayContainTheSeparator() {
        ValueMarker m = ValueMarker.parse("a@@@b@@@7@@@Main@@@main()V@@@0@@@Ljava/lang/String;@@@Main.java");
        assertEquals("a@@@b", m.getValue());
        assertEquals(7, m.getLine());
        assertTrue(m.isString());

        ValueMarker legacy = ValueMarker.parse("a@@@b@@@7@@@Main@@@main()V");
        assertEquals("a@@@b", legacy.getValue());
        assertEquals(7, legacy.getLine());
    }

    @Test
    void parsesLegacyFormat() {
        ValueMarker m = ValueMarker.parse("true@@@13@@@Main@@@main([Ljava/lang/String;)V");
        assertEquals("true", m.getValue());
        assertEquals(13, m.getLine());
        assertEquals("Main", m.getClassName());
        assertEquals(0, m.getCallIndex());
        assertNull(m.getTypeDesc());
        assertEquals("", m.getSourceFile());
    }

    @Test
    void rejectsGarbage() {
        assertThrows(IllegalArgumentException.class, () -> ValueMarker.parse("nonsense"));
    }

    @Test
    void parsesTarget() {
        TargetMarker t = TargetMarker.parse(
                "java.lang.AssertionError@@@Main@@Main.java@@23;pkg.Helper$Inner@@Helper.java@@5;java.lang.Thread@@@@-1");
        assertTrue(t.isAssertionError());
        assertEquals(3, t.getFrames().size());
        assertEquals("Main", t.getFrames().get(0).getClassName());
        assertEquals("Main.java", t.getFrames().get(0).getFileName());
        assertEquals(23, t.getFrames().get(0).getLine());
        assertEquals("", t.getFrames().get(2).getFileName());
        assertEquals(-1, t.getFrames().get(2).getLine());
    }

    @Test
    void targetWithoutFrames() {
        TargetMarker t = TargetMarker.parse("java.lang.RuntimeException@@@");
        assertEquals(0, t.getFrames().size());
    }
}
