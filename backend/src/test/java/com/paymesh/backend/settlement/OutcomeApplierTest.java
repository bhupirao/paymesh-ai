package com.paymesh.backend.settlement;

import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.repository.GatewayTransactionRepository;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OutcomeApplierTest {
    @ParameterizedTest
    @EnumSource(value = PaymentStatus.class, names = {"SUCCESS", "FAILED", "CANCELLED", "REFUNDED"})
    void terminalStatesCannotBeReversed(PaymentStatus status) {
        var transactions = mock(GatewayTransactionRepository.class);
        var ledger = mock(SimulatedGatewayLedger.class);
        var applier = new OutcomeApplier(transactions, ledger);
        Payment p = new Payment("M", "C", BigDecimal.TEN, "INR", "UPI");
        p.updateStatus(status);
        for (Observation observation : Observation.values()) {
            assertEquals("IGNORED", applier.apply(p, "MOCK_RAZORPAY", UUID.randomUUID(), observation, Instant.now()).status());
            assertEquals(status, p.getStatus());
        }
        verifyNoInteractions(transactions, ledger);
    }
}
