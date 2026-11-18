package com.paymesh.backend.settlement;

import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.entity.Payment;
import org.springframework.stereotype.Component;

/** Local durable simulation only. No provider SDK, HTTP client or real charge is used. */
@Component
public class SimulatedStatusLookup {
    private final SimulatedGatewayLedger ledger;

    public SimulatedStatusLookup(SimulatedGatewayLedger ledger) {
        this.ledger = ledger;
    }

    public SimulatedGatewayLedger.Lookup lookup(Payment payment, GatewayTransaction attempt) {
        String gateway = OutcomeApplier.gateway(payment, attempt);
        return ledger.lookup(payment.getPaymentId(), gateway).orElseGet(() -> {
            // Pre-V7 payments may have a persisted result but no simulation ledger entry.
            if (OutcomeApplier.terminal(attempt.getStatus()) && attempt.getGatewayTransactionId() != null) {
                return new SimulatedGatewayLedger.Lookup(attempt.getGatewayTransactionId(), Observation.valueOf(attempt.getStatus()));
            }
            return new SimulatedGatewayLedger.Lookup(attempt.getGatewayTransactionId(), Observation.UNKNOWN);
        });
    }
}
