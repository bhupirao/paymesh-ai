package com.paymesh.backend.investigation;

import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import static org.junit.jupiter.api.Assertions.*;

class AiInvestigationClientTest {
    ObjectMapper json=new ObjectMapper(); HttpServer server; String url;
    AtomicInteger calls=new AtomicInteger();
    String body; int status=200; long delay; long bodyDelay; String received;
    final String id="11111111-1111-4111-8111-111111111111";
    @BeforeEach void start() throws Exception {
        server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/v1/investigations", exchange -> {
            calls.incrementAndGet(); received=new String(exchange.getRequestBody().readAllBytes(),java.nio.charset.StandardCharsets.UTF_8);
            assertNull(exchange.getRequestHeaders().getFirst("Authorization"));
            try { Thread.sleep(delay); } catch(InterruptedException ex) { Thread.currentThread().interrupt(); }
            exchange.getResponseHeaders().set("Content-Type","application/json");
            byte[] bytes=body.getBytes(java.nio.charset.StandardCharsets.UTF_8);
            try {
                exchange.sendResponseHeaders(status,bytes.length);
                try { Thread.sleep(bodyDelay); } catch(InterruptedException ex) { Thread.currentThread().interrupt(); }
                exchange.getResponseBody().write(bytes);
            }
            finally { exchange.close(); }
        }); server.start(); url="http://127.0.0.1:"+server.getAddress().getPort(); body=valid().toString();
    }
    @AfterEach void stop() { server.stop(0); }
    ObjectNode valid() throws Exception { return (ObjectNode)camel(json.readTree(Files.readString(Path.of("../ai-service/tests/example-response.json")))); }
    JsonNode camel(JsonNode n) {
        if(n.isObject()) {
            ObjectNode out=json.createObjectNode(); n.fields().forEachRemaining(f -> {
                StringBuilder key=new StringBuilder(); boolean upper=false;
                for(char c:f.getKey().toCharArray()) { if(c=='_') upper=true; else { key.append(upper?Character.toUpperCase(c):c); upper=false; } }
                out.set(key.toString(),camel(f.getValue()));
            }); return out;
        }
        if(n.isArray()) { var a=json.createArrayNode(); n.forEach(v->a.add(camel(v))); return a; } return n;
    }
    AiInvestigationClient client(boolean enabled,int timeout,int max) { return new AiInvestigationClient(json,enabled,url,200,timeout,max); }
    ObjectNode evidence() { return json.createObjectNode().put("paymentId",id).put("amount","1234567890.12"); }
    @ParameterizedTest @ValueSource(strings={"RAG_LLM","RAG_ASSISTED","DETERMINISTIC"})
    void preservesActualModesAndExactRequest(String mode) throws Exception {
        var response=valid(); response.put("analysisMode",mode); response.put("generationStatus",mode.equals("RAG_LLM")?"SUCCEEDED":"UNAVAILABLE"); body=response.toString();
        assertEquals(mode,client(true,1000,262144).investigate(evidence()).path("analysisMode").asText());
        assertEquals("1234567890.12",json.readTree(received).path("amount").textValue()); assertEquals(1,calls.get());
    }
    @Test void disabledDoesNotCallService() { assertEquals(503,assertThrows(InvestigationFailure.class,()->client(false,1000,262144).investigate(evidence())).status()); assertEquals(0,calls.get()); }
    @Test void invalidJson() { body="{"; rejected(); }
    @Test void wrongPaymentId() throws Exception { body=valid().put("paymentId",UUID.randomUUID().toString()).toString(); rejected(); }
    @Test void missingRequiredField() throws Exception { var v=valid(); v.remove("customerView"); body=v.toString(); rejected(); }
    @Test void unknownEnum() throws Exception { body=valid().put("analysisMode","INVENTED").toString(); rejected(); }
    @Test void oversizedResponse() { body=" ".repeat(262145); rejected(); }
    @Test void nonSuccessStatus() { status=503; rejected(); }
    @Test void redirectNotFollowed() { status=302; rejected(); assertEquals(1,calls.get()); }
    @Test void timeout() { delay=300; assertThrows(InvestigationFailure.class,()->client(true,50,262144).investigate(evidence())); }
    @Test void responseBodyTimeout() { bodyDelay=300; assertThrows(InvestigationFailure.class,()->client(true,50,262144).investigate(evidence())); }
    @Test void unavailable() { server.stop(0); assertThrows(InvestigationFailure.class,()->client(true,100,262144).investigate(evidence())); }
    @Test void noRemoteCallInsideTransaction() {
        TransactionSynchronizationManager.setActualTransactionActive(true);
        try { assertThrows(IllegalStateException.class,()->client(true,100,262144).investigate(evidence())); }
        finally { TransactionSynchronizationManager.setActualTransactionActive(false); }
        assertEquals(0,calls.get());
    }
    @ParameterizedTest @ValueSource(strings={"http://example.com","http://localhost:8000","http://127.0.0.1:8000/path","http://user@127.0.0.1:8000","http://127.0.0.1:8000?x=y"})
    void rejectsUnsafeDestination(String target) { assertThrows(IllegalArgumentException.class,()->new AiInvestigationClient(json,true,target,100,100,1024)); }
    void rejected() { assertEquals(502,assertThrows(InvestigationFailure.class,()->client(true,1000,262144).investigate(evidence())).status()); }
}
