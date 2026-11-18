package com.paymesh.backend.settlement;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
public class WebhookSignatureVerifier {
    private final String razorpaySecret;
    private final String stripeSecret;

    public WebhookSignatureVerifier(
            @Value("${paymesh.webhooks.razorpay-secret:}") String razorpaySecret,
            @Value("${paymesh.webhooks.stripe-secret:}") String stripeSecret) {
        this.razorpaySecret = razorpaySecret;
        this.stripeSecret = stripeSecret;
    }

    public void verify(String gateway, String timestamp, String signature, byte[] body) {
        String secret = switch (gateway) {
            case "MOCK_RAZORPAY" -> razorpaySecret;
            case "MOCK_STRIPE" -> stripeSecret;
            default -> throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        };
        if (secret == null || secret.length() < 32) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Webhook secret is not configured");
        }
        try {
            Instant sent = Instant.ofEpochSecond(Long.parseLong(timestamp));
            Instant now = Instant.now();
            if (sent.isBefore(now.minusSeconds(300)) || sent.isAfter(now.plusSeconds(300))) {
                throw new IllegalArgumentException("Expired timestamp");
            }
            byte[] provided = HexFormat.of().parseHex(signature);
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            mac.update((timestamp + ".").getBytes(StandardCharsets.UTF_8));
            if (!MessageDigest.isEqual(mac.doFinal(body), provided)) {
                throw new IllegalArgumentException("Invalid signature");
            }
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid webhook signature or timestamp");
        }
    }
}
