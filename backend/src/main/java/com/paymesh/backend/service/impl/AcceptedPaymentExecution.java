package com.paymesh.backend.service.impl;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.enums.PaymentStatus;
import com.paymesh.backend.exception.PaymentGatewayException;
import com.paymesh.backend.gateway.*;
import com.paymesh.backend.service.internal.*;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
/** Trusted continuation ONLY after a durable authorized claim. No public callable execution method. */
@Service
public class AcceptedPaymentExecution {
 private final InternalPaymentService paymentService;private final PaymentGateway paymentGateway;private final InternalGatewayTransactionService gatewayTransactionService;private final DemoGatewayTimeoutSimulator demoTimeoutSimulator;
 @Autowired(required=false) private CheckoutSimulation checkoutSimulation;
 @Autowired public AcceptedPaymentExecution(InternalPaymentService core,PaymentGateway gateway,InternalGatewayTransactionService transactions,ObjectProvider<DemoGatewayTimeoutSimulator> simulator){this(core,gateway,transactions,simulator.getIfAvailable());}
 AcceptedPaymentExecution(InternalPaymentService core,PaymentGateway gateway,InternalGatewayTransactionService transactions,DemoGatewayTimeoutSimulator simulator){paymentService=core;paymentGateway=gateway;gatewayTransactionService=transactions;demoTimeoutSimulator=simulator;}
    PaymentResponse execute(PaymentResponse payment, String simulation) {
        UUID paymentId=payment.paymentId();
        if(simulation!=null&&checkoutSimulation==null)throw new IllegalStateException("Simulation unavailable");
        // Step 3: Persist gateway attempt before external call.
        GatewayTransaction transaction =
                gatewayTransactionService.initiateTransaction(
                        paymentId,
                        paymentGateway.getGatewayName()
                );

        // Step 4: Call gateway and persist its response.
        GatewayResponse gatewayResponse;

        try {
            gatewayResponse = "FAILED".equals(simulation) ? checkoutSimulation.failed(payment) : paymentGateway.processPayment(
                    paymentId,
                    payment.amount(),
                    payment.currency()
            );

        } catch (Exception ex) {

            // Outcome may be unknown.
            // Do not mark payment FAILED.
            gatewayTransactionService.markTransactionUnknown(
                    transaction.getId(),
                    ex.getMessage()
            );

            throw new PaymentGatewayException(
                    "Payment gateway processing failed; " +
                            "payment outcome requires reconciliation",
                    ex
            );
        }

        if("TIMEOUT".equals(simulation))gatewayResponse=checkoutSimulation.timeout(gatewayResponse);

        // RoutingPaymentGateway has already persisted the actual provider outcome
        // and UUID to the simulated ledger. Alter only the orchestration observation.
        if (demoTimeoutSimulator != null) {
            gatewayResponse = demoTimeoutSimulator.observe(payment.customerId(), gatewayResponse);
        }

        // Step 5: Save gateway result.
        gatewayTransactionService.completeTransaction(
                transaction.getId(),
                gatewayResponse
        );

        // Step 6: Update business payment status.
        if (gatewayResponse.status() == GatewayStatus.SUCCESS) {

            return finishPayment(
                    paymentId,
                    PaymentStatus.SUCCESS
            );
        }

        if (gatewayResponse.status() == GatewayStatus.FAILED) {

            return finishPayment(
                    paymentId,
                    PaymentStatus.FAILED
            );
        }

        // TIMEOUT: Keep payment PROCESSING.
        return paymentService.getPaymentById(paymentId);
    }

    private PaymentResponse finishPayment(UUID paymentId, PaymentStatus outcome) {
        try {
            return paymentService.updatePaymentStatus(paymentId, outcome);
        } catch (IllegalStateException ex) {
            // Keep the public lifecycle validator strict. Only orchestration tolerates
            // a terminal result already committed by an asynchronous settlement/refund.
            PaymentResponse current = paymentService.getPaymentById(paymentId);
            PaymentStatus status = PaymentStatus.valueOf(current.status());
            if (status == PaymentStatus.SUCCESS || status == PaymentStatus.FAILED
                    || status == PaymentStatus.CANCELLED || status == PaymentStatus.REFUNDED) {
                return current;
            }
            throw ex;
        }
    }
}
