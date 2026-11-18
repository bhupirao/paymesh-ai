package com.paymesh.backend.service.impl;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.gateway.*;
import com.paymesh.backend.settlement.SimulatedGatewayLedger;
import java.util.UUID;
import org.springframework.stereotype.Component;
/** Only invoked with an already gate-validated, durably accepted simulation choice. */
@Component
class CheckoutSimulation {
 private final GatewayRouter router;private final SimulatedGatewayLedger ledger;
 CheckoutSimulation(GatewayRouter router,SimulatedGatewayLedger ledger){this.router=router;this.ledger=ledger;}
 GatewayResponse failed(PaymentResponse p){var r=new GatewayResponse(UUID.randomUUID(),router.route(p.currency()).getGatewayName(),GatewayStatus.FAILED,"SIMULATED_DECLINE","Simulated payment declined");ledger.record(p.paymentId(),r);return r;}
 GatewayResponse timeout(GatewayResponse actual){return new DemoGatewayTimeoutSimulator().observe(DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID,actual);}
}
