package com.paymesh.backend.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
import java.util.concurrent.Semaphore;
import org.springframework.web.bind.annotation.*;
import org.springframework.transaction.annotation.*;

@RestController
public class InvestigationController {
    private final EvidenceCollector collector;
    private final AiInvestigationClient client;
    private final AiRequestBudget capacity;
    @org.springframework.beans.factory.annotation.Autowired
    public InvestigationController(EvidenceCollector collector, AiInvestigationClient client,AiRequestBudget capacity) { this.collector=collector; this.client=client;this.capacity=capacity; }
    public InvestigationController(EvidenceCollector collector,AiInvestigationClient client){this(collector,client,new AiRequestBudget());}
    public record Provenance(String source, String collectedAt, Map<String,String> unavailableEvidence, String scope) {}
    public record Response(Provenance evidenceProvenance, JsonNode investigation) {}
    @PostMapping("/api/v1/payments/{paymentId}/investigate")
    @Transactional(propagation = Propagation.NEVER)
    public Response investigate(@PathVariable UUID paymentId) {
        // Authorization precedes admission and all remote calls, including when disabled/busy.
        var snapshot = collector.collect(paymentId);
        if (!capacity.acquire()) throw new InvestigationFailure(503, "AI investigation capacity is busy; try later");
        try {
            return new Response(new Provenance("JAVA_AUTHORIZED_DATABASE_SNAPSHOT", snapshot.evidence().path("collectedAt").asText(),
                    snapshot.unavailable(), "Java authenticated and authorized collection. Python does not authenticate direct input. Bank debit, settlement and refund arrival remain unverified."),
                    client.investigate(snapshot.evidence()));
        } finally { capacity.release(); }
    }
}
