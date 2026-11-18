package com.paymesh.backend.security.auth;

import java.time.*;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class LoginRateLimiterTest {
    static final class MutableClock extends Clock {
        Instant value = Instant.parse("2026-01-01T00:00:00Z");
        @Override public ZoneId getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(ZoneId zone) { return this; }
        @Override public Instant instant() { return value; }
    }

    @Test
    void retriesHaveBudgetExpiryAndBoundedClientMemory() {
        MutableClock clock = new MutableClock();
        LoginRateLimiter limiter = new LoginRateLimiter(2, 60, 1, clock);
        assertTrue(limiter.acquire("client-a").allowed());
        assertTrue(limiter.acquire("client-a").allowed());
        assertFalse(limiter.acquire("client-a").allowed());
        assertEquals(60, limiter.acquire("client-a").retryAfterSeconds());
        assertFalse(limiter.acquire("client-b").allowed(), "Capacity exhaustion must fail closed");
        clock.value = clock.value.plusSeconds(60);
        assertTrue(limiter.acquire("client-b").allowed());
        assertThrows(IllegalArgumentException.class, () -> new LoginRateLimiter(0, 60, 1, clock));
    }

    @Test
    void concurrentRequestsCannotExceedBudget() throws Exception {
        LoginRateLimiter limiter = new LoginRateLimiter(5, 60, 100, Clock.systemUTC());
        ExecutorService pool = Executors.newFixedThreadPool(10);
        try {
            List<Callable<Boolean>> tasks = new ArrayList<>();
            for (int i = 0; i < 100; i++) tasks.add(() -> limiter.acquire("same-client").allowed());
            int accepted = 0;
            for (Future<Boolean> future : pool.invokeAll(tasks)) if (future.get()) accepted++;
            assertEquals(5, accepted);
        } finally {
            pool.shutdownNow(); assertTrue(pool.awaitTermination(10, TimeUnit.SECONDS));
        }
    }
}
