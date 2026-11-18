package com.paymesh.backend.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

/** Enforce the Python request constraints before any remote call. */
final class EvidenceValidator {
    private static final String PAYMENT = "CREATED PROCESSING SUCCESS FAILED CANCELLED REFUNDED";
    private EvidenceValidator() {}
    static void validate(JsonNode e) {
        try {
            UUID.fromString(e.path("paymentId").asText());
            money(e.path("amount"),14);
            check(e.path("currency").asText().matches("[A-Z]{3}"));
            one(e,"paymentStatus",PAYMENT); shortText(e,"paymentMethod");
            Instant collected=Instant.parse(e.path("collectedAt").asText());
            BigDecimal total=BigDecimal.ZERO;
            for(String field:List.of("gatewayTransactions","refunds","webhooks","reconciliation")) {
                JsonNode rows=e.get(field); if(rows.isNull()) continue;
                check(rows.isArray() && rows.size()<=100); Set<UUID> ids=new HashSet<>();
                for(JsonNode r:rows) {
                    check(ids.add(UUID.fromString(r.path(field.equals("refunds") ? "refundId" : "id").asText())));
                    check(e.get("paymentId").equals(r.get("paymentId")));
                    for(String t:List.of("createdAt","updatedAt","occurredAt")) if(r.has(t)) check(!Instant.parse(r.get(t).asText()).isAfter(collected));
                    switch(field) {
                        case "gatewayTransactions" -> {
                            shortText(r,"gatewayName"); one(r,"status","SUCCESS FAILED TIMEOUT");
                            if(!r.path("gatewayTransactionId").isNull()) UUID.fromString(r.path("gatewayTransactionId").asText());
                            check(!Instant.parse(r.path("updatedAt").asText()).isBefore(Instant.parse(r.path("createdAt").asText())));
                        }
                        case "refunds" -> { money(r.get("amount"),19); one(r,"status","SUCCESS"); total=total.add(new BigDecimal(r.get("amount").asText())); }
                        case "webhooks" -> {
                            UUID.fromString(r.path("gatewayTransactionId").asText()); one(r,"status","RECEIVED PROCESSED IGNORED DEFERRED FAILED");
                            one(r,"outcome","SUCCESS FAILED TIMEOUT UNKNOWN");
                        }
                        case "reconciliation" -> {
                            one(r,"statusBefore",PAYMENT); one(r,"statusAfter",PAYMENT); one(r,"result","RESOLVED RETRY EXHAUSTED SKIPPED");
                            if(!r.path("outcome").isNull()) one(r,"outcome","SUCCESS FAILED TIMEOUT UNKNOWN");
                        }
                    }
                }
            }
            check(total.compareTo(new BigDecimal(e.path("amount").asText()))<=0);
        } catch(RuntimeException ex) { throw new InvestigationFailure(422,"Stored evidence cannot satisfy the investigation contract"); }
    }
    private static void money(JsonNode n,int digits) { check(n.isTextual()); BigDecimal d=new BigDecimal(n.asText()); check(d.signum()>0 && d.scale()<=2 && d.precision()<=digits); }
    private static void shortText(JsonNode n,String k) { String s=n.path(k).asText(); check(!s.isBlank() && s.length()<=100); }
    private static void one(JsonNode n,String k,String options) { check(List.of(options.split(" ")).contains(n.path(k).asText())); }
    private static void check(boolean ok) { if(!ok) throw new IllegalArgumentException(); }
}
