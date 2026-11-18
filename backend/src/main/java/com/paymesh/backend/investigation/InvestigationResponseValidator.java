package com.paymesh.backend.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.OffsetDateTime;
import java.util.*;

final class InvestigationResponseValidator {
    private InvestigationResponseValidator() {}
    static void validate(JsonNode n, String paymentId) {
        try {
            object(n, "investigationId paymentId investigationStatus scenario generatedAt customerView technicalView evidenceReferences limitations analysisMode knowledgeReferences generationStatus");
            UUID.fromString(text(n, "investigationId")); UUID.fromString(text(n, "paymentId"));
            require(paymentId.equals(text(n, "paymentId")));
            OffsetDateTime.parse(text(n, "generatedAt"));
            one(n, "investigationStatus", "COMPLETED INCONCLUSIVE");
            one(n, "scenario", "CREATED PROCESSING GATEWAY_TIMEOUT SUCCESS WEBHOOK_RECOVERY RECONCILIATION_RECOVERY FAILED PARTIAL_REFUND FULL_REFUND UNRESOLVED_REFUND INCONCLUSIVE");
            one(n, "analysisMode", "DETERMINISTIC RAG_ASSISTED RAG_LLM");
            one(n, "generationStatus", "DISABLED NOT_ATTEMPTED SUCCEEDED NO_RELEVANT_CONTEXT RETRIEVAL_UNAVAILABLE TIMEOUT UNAVAILABLE INVALID_RESPONSE VALIDATION_FAILED CONTEXT_LIMIT");
            require(!"RAG_LLM".equals(text(n,"analysisMode")) || "SUCCEEDED".equals(text(n,"generationStatus")));
            JsonNode c = n.get("customerView"), t = n.get("technicalView");
            object(c, "title summary whatHappened nextAction requiresUserAction");
            for (String key : List.of("title", "summary", "whatHappened", "nextAction")) text(c,key);
            require(c.get("requiresUserAction").isBoolean());
            object(t, "observedPaymentStatus rootCause rootCauseCertainty supportingEvidence technicalExplanation recommendedActions certainty");
            one(t,"observedPaymentStatus","CREATED PROCESSING SUCCESS FAILED CANCELLED REFUNDED");
            one(t,"rootCauseCertainty","CONFIRMED LIKELY INCONCLUSIVE"); one(t,"certainty","CONFIRMED LIKELY INCONCLUSIVE");
            text(t,"rootCause"); text(t,"technicalExplanation"); strings(t.get("supportingEvidence")); strings(t.get("recommendedActions"));
            strings(n.get("evidenceReferences")); strings(n.get("limitations"));
            require(n.get("knowledgeReferences").isArray());
            for (JsonNode k : n.get("knowledgeReferences")) {
                object(k,"documentId chunkId title sources score"); text(k,"documentId"); text(k,"chunkId"); text(k,"title");
                strings(k.get("sources")); require(k.get("score").isNumber() && Double.isFinite(k.get("score").asDouble()));
            }
        } catch (RuntimeException ex) { throw new InvestigationFailure(502,"Invalid AI service response"); }
    }
    private static void object(JsonNode n, String fields) {
        require(n != null && n.isObject()); Set<String> expected = new HashSet<>(List.of(fields.split(" ")));
        Set<String> actual = new HashSet<>(); n.fieldNames().forEachRemaining(actual::add); require(expected.equals(actual));
    }
    private static String text(JsonNode n, String key) { JsonNode v=n.get(key); require(v != null && v.isTextual() && !v.asText().isBlank()); return v.asText(); }
    private static void strings(JsonNode n) { require(n != null && n.isArray()); n.forEach(v -> require(v.isTextual())); }
    private static void one(JsonNode n, String key, String values) { require(List.of(values.split(" ")).contains(text(n,key))); }
    private static void require(boolean valid) { if (!valid) throw new IllegalArgumentException(); }
}
