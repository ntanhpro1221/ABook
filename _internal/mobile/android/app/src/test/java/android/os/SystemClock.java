package android.os;

public final class SystemClock {
    public static long elapsedRealtime() { return Handler.now; }
    public static long uptimeMillis() { return Handler.now; }
}
