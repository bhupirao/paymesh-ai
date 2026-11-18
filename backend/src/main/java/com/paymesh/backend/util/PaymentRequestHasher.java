
package com.paymesh.backend.util;

import com.paymesh.backend.dto.PaymentRequest;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

@Component
public class PaymentRequestHasher {

    public String hash(PaymentRequest request) {

        String canonicalRequest = String.join("|",
                encode(request.merchantId()),
                normalizeAmount(request.amount()),
                encode(request.currency()),
                encode(request.customerId()),
                encode(request.paymentMethod())
        );

        try {
            MessageDigest digest =
                    MessageDigest.getInstance("SHA-256");

            byte[] hashBytes = digest.digest(
                    canonicalRequest.getBytes(StandardCharsets.UTF_8)
            );

            return HexFormat.of().formatHex(hashBytes);

        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(
                    "SHA-256 algorithm is unavailable", ex
            );
        }
    }

    private String normalizeAmount(BigDecimal amount) {
        return amount.stripTrailingZeros().toPlainString();
    }

    private String encode(String value) {
        return value.length() + ":" + value;
    }
}
