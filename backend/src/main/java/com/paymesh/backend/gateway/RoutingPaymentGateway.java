package com.paymesh.backend.gateway;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Component;
import java.math.BigDecimal;
import java.util.UUID;
import com.paymesh.backend.settlement.SimulatedGatewayLedger;
@Primary
@Component
public class RoutingPaymentGateway implements PaymentGateway {
    private final MockRazorpayGateway razorpay;
    private final MockStripeGateway stripe;
    private final SimulatedGatewayLedger ledger;
    public RoutingPaymentGateway(MockRazorpayGateway razorpay, MockStripeGateway stripe, SimulatedGatewayLedger ledger) {
        this.razorpay = razorpay; this.stripe = stripe; this.ledger = ledger;
    }
    @Override public String getGatewayName() { return "MOCK_ROUTER"; }
    @Override public GatewayResponse processPayment(UUID paymentId, BigDecimal amount, String currency) {
        GatewayResponse response;
        if ("INR".equalsIgnoreCase(currency)) response = razorpay.processPayment(paymentId,amount,currency);
        else if ("USD".equalsIgnoreCase(currency)) response = stripe.processPayment(paymentId,amount,currency);
        else response = new GatewayResponse(null,getGatewayName(),GatewayStatus.FAILED,"UNSUPPORTED_CURRENCY","No gateway for currency: " + currency);
        ledger.record(paymentId, response);
        return response;
    }
}
