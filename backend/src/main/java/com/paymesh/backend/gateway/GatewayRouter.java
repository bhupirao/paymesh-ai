package com.paymesh.backend.gateway;
import org.springframework.stereotype.Component;
import java.util.List;
@Component
public class GatewayRouter {
    private final List<PaymentGateway> gateways;
    public GatewayRouter(List<PaymentGateway> gateways) { this.gateways = gateways; }
    public PaymentGateway route(String currency) {
        String name = switch (currency == null ? "" : currency.toUpperCase(java.util.Locale.ROOT)) {
            case "INR" -> "MOCK_RAZORPAY";
            case "USD" -> "MOCK_STRIPE";
            default -> throw new IllegalArgumentException("No simulated gateway configured for currency: " + currency);
        };
        return gateways.stream().filter(g -> name.equals(g.getGatewayName())).findFirst()
            .orElseThrow(() -> new IllegalStateException("Missing gateway: " + name));
    }
}
