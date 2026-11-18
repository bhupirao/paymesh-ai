package com.paymesh.backend.service.impl;

import com.paymesh.backend.entity.GatewayTransaction;
import com.paymesh.backend.gateway.GatewayResponse;
import com.paymesh.backend.repository.GatewayTransactionRepository;
import com.paymesh.backend.security.business.*;
import com.paymesh.backend.service.GatewayTransactionService;
import com.paymesh.backend.service.internal.InternalGatewayTransactionService;
import java.util.List;
import java.util.UUID;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Primary
@Transactional(isolation = Isolation.READ_COMMITTED)
public class GatewayTransactionServiceImpl implements GatewayTransactionService {
    private final InternalGatewayTransactionService core;
    private final BusinessAccess access;
    private final GatewayTransactionRepository transactions;
    public GatewayTransactionServiceImpl(InternalGatewayTransactionService core, BusinessAccess access, GatewayTransactionRepository transactions) {
        this.core = core; this.access = access; this.transactions = transactions;
    }
    @Override public GatewayTransaction initiateTransaction(UUID id, String gateway) {
        var actor = access.actor(); var payment = access.payment(actor, id, true);
        var result = core.initiateTransaction(id, gateway);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_GATEWAY_ATTEMPT_CREATED"); return result;
    }
    @Override public GatewayTransaction completeTransaction(UUID id, GatewayResponse response) {
        var actor = access.actor(); var transaction = transaction(actor, id);
        var payment = access.payment(actor, transaction.getPaymentId(), true);
        var result = core.completeTransaction(id, response);
        access.audit(actor, payment.getMerchantId(), payment.getPaymentId(), "ADMIN_GATEWAY_ATTEMPT_COMPLETED"); return result;
    }
    @Override public GatewayTransaction markTransactionUnknown(UUID id, String message) {
        var actor = access.actor(); var transaction = transaction(actor, id);
        var payment = access.payment(actor, transaction.getPaymentId(), true);
        var result = core.markTransactionUnknown(id, message);
        access.audit(actor, payment.getMerchantId(), payment.getPaymentId(), "ADMIN_GATEWAY_ATTEMPT_UNKNOWN"); return result;
    }
    @Override public List<GatewayTransaction> getTransactionsByPaymentId(UUID id) {
        var actor = access.actor(); var payment = access.payment(actor, id, false);
        var result = core.getTransactionsByPaymentId(id);
        access.audit(actor, payment.getMerchantId(), id, "ADMIN_GATEWAY_HISTORY_READ"); return result;
    }
    private GatewayTransaction transaction(BusinessAccess.Actor actor, UUID id) {
        return transactions.findAccessibleById(id, actor.id(), actor.version(), actor.admin(), actor.merchant())
                .orElseThrow(BusinessResourceNotFoundException::new);
    }
}
