package com.paymesh.backend.settlement;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/webhooks")
public class WebhookController {
    private final WebhookIngress ingress;
    public WebhookController(WebhookIngress ingress) { this.ingress = ingress; }

    @PostMapping("/mock-razorpay")
    public ResponseEntity<WebhookInbox.Receipt> razorpay(
            @RequestHeader("X-Paymesh-Timestamp") String timestamp,
            @RequestHeader("X-Paymesh-Signature") String signature, @RequestBody byte[] body) {
        return accept("MOCK_RAZORPAY", timestamp, signature, body);
    }

    @PostMapping("/mock-stripe")
    public ResponseEntity<WebhookInbox.Receipt> stripe(
            @RequestHeader("X-Paymesh-Timestamp") String timestamp,
            @RequestHeader("X-Paymesh-Signature") String signature, @RequestBody byte[] body) {
        return accept("MOCK_STRIPE", timestamp, signature, body);
    }

    private ResponseEntity<WebhookInbox.Receipt> accept(String gateway, String timestamp, String signature, byte[] body) {
        var receipt = ingress.receive(gateway, timestamp, signature, body);
        return ResponseEntity.status(receipt.status().equals("RECEIVED") || receipt.status().equals("DEFERRED") ? 202 : 200)
                .body(receipt);
    }
}
