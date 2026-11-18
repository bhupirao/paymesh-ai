package com.paymesh.backend.service.impl;
import com.paymesh.backend.dto.PaymentResponse;
import com.paymesh.backend.gateway.PaymentGateway;
import com.paymesh.backend.gateway.DemoGatewayTimeoutSimulator;
import com.paymesh.backend.service.PaymentOrchestrationService;
import com.paymesh.backend.service.internal.InternalPaymentService;
import com.paymesh.backend.service.internal.InternalGatewayTransactionService;
import com.paymesh.backend.security.business.BusinessProcessingClaims;
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import java.util.UUID;
@Service
public class PaymentOrchestrationServiceImpl implements PaymentOrchestrationService {
 private final BusinessProcessingClaims claims;private AcceptedPaymentExecution execution;
 @Autowired public PaymentOrchestrationServiceImpl(InternalPaymentService core,PaymentGateway gateway,InternalGatewayTransactionService transactions,BusinessProcessingClaims claims,ObjectProvider<DemoGatewayTimeoutSimulator> simulator){this.claims=claims;execution=new AcceptedPaymentExecution(core,gateway,transactions,simulator.getIfAvailable());}
 public PaymentOrchestrationServiceImpl(InternalPaymentService core,PaymentGateway gateway,InternalGatewayTransactionService transactions,BusinessProcessingClaims claims){this.claims=claims;execution=new AcceptedPaymentExecution(core,gateway,transactions,(DemoGatewayTimeoutSimulator)null);}
 @Autowired void sharedExecution(AcceptedPaymentExecution shared){execution=shared;}
 @Override public PaymentResponse processPayment(UUID id){return execution.execute(claims.claim(id),null);}
}
