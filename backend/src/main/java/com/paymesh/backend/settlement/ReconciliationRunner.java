package com.paymesh.backend.settlement;

import com.paymesh.backend.exception.PaymentNotFoundException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class ReconciliationRunner {
    private static final Logger log = LoggerFactory.getLogger(ReconciliationRunner.class);
    private final ReconciliationService service;
    public ReconciliationRunner(ReconciliationService service) { this.service = service; }

    public ReconciliationService.Report run(UUID id) {
        try {
            return service.reconcile(id);
        } catch (PaymentNotFoundException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            log.warn("Reconciliation failed for payment {} ({})", id, ex.getClass().getSimpleName());
            // A new transaction records a failed attempt even if the work transaction rolled back.
            return service.failed(id);
        }
    }
}
