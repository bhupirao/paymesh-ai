package com.paymesh.backend.settlement;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.HexFormat;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.*;

class WebhookSignatureVerifierTest {
    static final String RAZORPAY = "razorpay-test-secret-with-at-least-32-characters";
    static final String STRIPE = "stripe-test-secret-with-at-least-32-characters";
    private final WebhookSignatureVerifier verifier = new WebhookSignatureVerifier(RAZORPAY, STRIPE);

    static String sign(String secret, String timestamp, byte[] body) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        mac.update((timestamp + ".").getBytes(StandardCharsets.UTF_8));
        return HexFormat.of().formatHex(mac.doFinal(body));
    }

    @Test
    void acceptsBothProvidersAndExactRawBytes() throws Exception {
        byte[] body = "{\"eventId\":\"évent\"}\n".getBytes(StandardCharsets.UTF_8);
        String timestamp = Long.toString(Instant.now().getEpochSecond());
        verifier.verify("MOCK_RAZORPAY", timestamp, sign(RAZORPAY, timestamp, body), body);
        verifier.verify("MOCK_STRIPE", timestamp, sign(STRIPE, timestamp, body), body);
    }

    @Test
    void rejectsTamperingWrongProviderAndMalformedSignatures() throws Exception {
        byte[] body = "{}".getBytes(StandardCharsets.UTF_8);
        String timestamp = Long.toString(Instant.now().getEpochSecond());
        String signature = sign(RAZORPAY, timestamp, body);
        assertEquals(401, assertThrows(ResponseStatusException.class,
                () -> verifier.verify("MOCK_STRIPE", timestamp, signature, body)).getStatusCode().value());
        assertThrows(ResponseStatusException.class, () -> verifier.verify("MOCK_RAZORPAY", timestamp, signature, "{ }".getBytes()));
        for (String invalid : new String[]{"", "00", "z".repeat(64), "0".repeat(64)}) {
            assertThrows(ResponseStatusException.class, () -> verifier.verify("MOCK_RAZORPAY", timestamp, invalid, body));
        }
    }

    @Test
    void rejectsOldAndFutureSignaturesEvenWhenHmacIsCorrect() throws Exception {
        byte[] body = "{}".getBytes(StandardCharsets.UTF_8);
        for (long offset : new long[]{-600, 600}) {
            String timestamp = Long.toString(Instant.now().plusSeconds(offset).getEpochSecond());
            String signature = sign(RAZORPAY, timestamp, body);
            assertThrows(ResponseStatusException.class, () -> verifier.verify("MOCK_RAZORPAY", timestamp, signature, body));
        }
        assertThrows(ResponseStatusException.class, () -> verifier.verify("MOCK_RAZORPAY", "not-a-time", "00", body));
        assertThrows(ResponseStatusException.class, () -> verifier.verify("MOCK_RAZORPAY", Long.toString(Long.MAX_VALUE), "00", body));
    }

    @Test
    void missingSecretsFailClosed() {
        var disabled = new WebhookSignatureVerifier("", "short");
        assertEquals(503, assertThrows(ResponseStatusException.class,
                () -> disabled.verify("MOCK_RAZORPAY", "0", "00", new byte[0])).getStatusCode().value());
        assertEquals(503, assertThrows(ResponseStatusException.class,
                () -> disabled.verify("MOCK_STRIPE", "0", "00", new byte[0])).getStatusCode().value());
    }
}
