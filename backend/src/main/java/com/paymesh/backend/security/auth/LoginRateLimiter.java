package com.paymesh.backend.security.auth;

import java.time.Clock;
import java.util.HashMap;
import java.util.Map;

/** Bounded single-instance budget; never trusts X-Forwarded-For supplied by clients. */
final class LoginRateLimiter {
    private final Map<String, Bucket> clients = new HashMap<>();
    private final int attempts;
    private final int maxClients;
    private final long seconds;
    private final Clock clock;
    private long lastCleanup = Long.MIN_VALUE;

    LoginRateLimiter(int attempts, long seconds, int maxClients, Clock clock) {
        if (attempts < 1 || attempts > 100 || seconds < 1 || seconds > 3600 || maxClients < 1 || maxClients > 100000) {
            throw new IllegalArgumentException("Invalid login rate limit configuration");
        }
        this.attempts = attempts; this.seconds = seconds; this.maxClients = maxClients; this.clock = clock;
    }

    synchronized Decision acquire(String remoteAddress) {
        long now = clock.instant().getEpochSecond();
        String key = remoteAddress == null || remoteAddress.length() > 64 ? "unknown" : remoteAddress;
        if (now != lastCleanup) {
            clients.entrySet().removeIf(e -> now - e.getValue().started >= seconds);
            lastCleanup = now;
        }
        Bucket bucket = clients.get(key);
        if (bucket == null) {
            if (clients.size() >= maxClients) return new Decision(false, seconds);
            bucket = new Bucket(now); clients.put(key, bucket);
        }
        long retry = Math.max(1, seconds - (now - bucket.started));
        if (bucket.used >= attempts) return new Decision(false, retry);
        bucket.used++;
        return new Decision(true, 0);
    }

    private static final class Bucket {
        final long started; int used;
        Bucket(long started) { this.started = started; }
    }
    record Decision(boolean allowed, long retryAfterSeconds) {}
}
