package android.os;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Deterministic Android main queue; reset by MusicBedIntegrationTest around each test. */
public class Handler {
    static long now;
    private static final class Job {
        final Handler owner; final Runnable task; final long at;
        Job(Handler owner, Runnable task, long at) { this.owner = owner; this.task = task; this.at = at; }
    }
    private static final List<Job> jobs = new ArrayList<>();
    public Handler() {}
    public Handler(Looper looper) {}
    public boolean post(Runnable task) { return postDelayed(task, 0); }
    public boolean postDelayed(Runnable task, long delay) { jobs.add(new Job(this, task, now + delay)); return true; }
    public void removeCallbacks(Runnable task) { jobs.removeIf(job -> job.owner == this && job.task == task); }
    public void removeCallbacksAndMessages(Object token) { jobs.removeIf(job -> job.owner == this); }
    public static void reset() { jobs.clear(); now = 0; }
    public static void advance(long ms) {
        long end = now + ms;
        while (true) {
            Job next = jobs.stream().filter(job -> job.at <= end).min(Comparator.comparingLong(job -> job.at)).orElse(null);
            if (next == null) break;
            jobs.remove(next); now = next.at; next.task.run();
        }
        now = end;
    }
}
