package com.paymesh.backend.investigation;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.*;
import java.net.*;
import java.net.http.HttpClient;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.client.RestClient;

@Component
public class AiInvestigationClient {
    private final RestClient client;
    private final ObjectMapper json;
    private final boolean enabled;
    private final int maxBytes;
    public AiInvestigationClient(ObjectMapper json,
            @Value("${paymesh.ai.enabled:false}") boolean enabled,
            @Value("${paymesh.ai.base-url:http://127.0.0.1:8000}") String baseUrl,
            @Value("${paymesh.ai.connect-timeout-ms:2000}") int connectMs,
            @Value("${paymesh.ai.response-timeout-ms:45000}") int responseMs,
            @Value("${paymesh.ai.max-response-bytes:262144}") int maxBytes) {
        URI uri = URI.create(baseUrl);
        if (!"http".equals(uri.getScheme()) || !"127.0.0.1".equals(uri.getHost()) || uri.getUserInfo() != null
                || uri.getQuery() != null || uri.getFragment() != null || !(uri.getPath().isEmpty() || "/".equals(uri.getPath())))
            throw new IllegalArgumentException("AI base URL must be an HTTP IPv4 loopback origin");
        if (connectMs < 1 || connectMs > 10000 || responseMs < 1 || responseMs > 120000 || maxBytes < 1024 || maxBytes > 1048576)
            throw new IllegalArgumentException("Invalid AI client bounds");
        this.json = json.copy().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
                .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
        this.enabled = enabled; this.maxBytes = maxBytes;
        var http = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectMs))
                .followRedirects(HttpClient.Redirect.NEVER).proxy(new ProxySelector() {
                    public List<Proxy> select(URI target) { return List.of(Proxy.NO_PROXY); }
                    public void connectFailed(URI target, SocketAddress address, java.io.IOException error) { }
                }).build();
        var factory = new JdkClientHttpRequestFactory(http); factory.setReadTimeout(Duration.ofMillis(responseMs));
        client = RestClient.builder().requestFactory(factory).baseUrl(baseUrl).build();
    }
    public JsonNode investigate(JsonNode evidence) {
        if (TransactionSynchronizationManager.isActualTransactionActive()) throw new IllegalStateException("Remote AI call inside database transaction");
        if (!enabled) throw new InvestigationFailure(503, "AI investigation is disabled");
        try {
            byte[] requestBody;
            try { requestBody = json.writeValueAsBytes(evidence); }
            catch (java.io.IOException ex) { throw new InvestigationFailure(422, "Invalid investigation evidence"); }
            if (requestBody.length > 131072) throw new InvestigationFailure(422, "Investigation evidence exceeds Python request size limit");
            return client.post().uri("/api/v1/investigations").contentType(MediaType.APPLICATION_JSON)
                    .body(requestBody).exchange((request, response) -> {
                        if (!response.getStatusCode().is2xxSuccessful()) throw new InvestigationFailure(502, "AI service rejected the investigation");
                        if (response.getHeaders().getContentType() == null || !MediaType.APPLICATION_JSON.isCompatibleWith(response.getHeaders().getContentType()))
                            throw new InvestigationFailure(502, "Invalid AI service response");
                        byte[] bytes = response.getBody().readNBytes(maxBytes + 1);
                        if (bytes.length > maxBytes) throw new InvestigationFailure(502, "AI service response exceeds size limit");
                        JsonNode result = json.readTree(bytes);
                        InvestigationResponseValidator.validate(result, evidence.path("paymentId").asText());
                        return result;
                    });
        } catch (InvestigationFailure ex) { throw ex; }
        catch (RuntimeException ex) { throw new InvestigationFailure(502, "AI service unavailable or response invalid"); }
    }
}
