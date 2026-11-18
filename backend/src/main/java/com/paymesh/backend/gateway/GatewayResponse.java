
package com.paymesh.backend.gateway;

import java.util.UUID;

public record GatewayResponse(
        UUID gatewayTransactionId,
        String gatewayName,
        GatewayStatus status,
        String errorCode,
        String errorMessage
) {
}
