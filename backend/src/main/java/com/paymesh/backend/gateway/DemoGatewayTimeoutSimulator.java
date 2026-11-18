package com.paymesh.backend.gateway;

import java.util.UUID;

/**
 * Converts the observed response for one reserved demo customer into a timeout.
 * The simulated gateway's real result must already have been recorded before this
 * class is called. This class is only registered by the guarded demo profile.
 */
public final class DemoGatewayTimeoutSimulator {
    public static final String RESERVED_CUSTOMER_ID = "PAYMESH_DEMO_GATEWAY_TIMEOUT";

    public GatewayResponse observe(String customerId, GatewayResponse actualResponse) {
        if (!RESERVED_CUSTOMER_ID.equals(customerId)
                || actualResponse == null
                || actualResponse.status() != GatewayStatus.SUCCESS
                || actualResponse.gatewayTransactionId() == null
                || !("MOCK_RAZORPAY".equals(actualResponse.gatewayName())
                    || "MOCK_STRIPE".equals(actualResponse.gatewayName()))) {
            return actualResponse;
        }
        return new GatewayResponse(actualResponse.gatewayTransactionId(),
                actualResponse.gatewayName(), GatewayStatus.TIMEOUT,
                "DEMO_SIMULATED_TIMEOUT", "Simulated gateway response timeout");
    }
}
