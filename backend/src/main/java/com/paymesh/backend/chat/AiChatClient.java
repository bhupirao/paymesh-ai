package com.paymesh.backend.chat;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.core.JsonParser;
import java.net.*;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import org.springframework.transaction.support.TransactionSynchronizationManager;
@Component public class AiChatClient {
 private final ObjectMapper json;private final RestClient client;private final boolean enabled;private final int maxBytes;private final String secret;
 public AiChatClient(ObjectMapper json,@Value("${paymesh.ai.chat.enabled:false}")boolean enabled,@Value("${paymesh.ai.base-url:http://127.0.0.1:8000}")String base,@Value("${paymesh.ai.connect-timeout-ms:2000}")int connect,@Value("${paymesh.ai.chat.response-timeout-ms:25000}")int read,@Value("${paymesh.ai.chat.max-response-bytes:65536}")int max,@Value("${paymesh.ai.chat.service-token:}")String secret){
  URI uri=URI.create(base);if(!"http".equals(uri.getScheme())||!"127.0.0.1".equals(uri.getHost())||uri.getUserInfo()!=null||uri.getQuery()!=null||uri.getFragment()!=null||!Set.of("","/").contains(uri.getPath())||uri.getPort()<1||Set.of(8080,8082,18080,5432,5500).contains(uri.getPort()))throw new IllegalArgumentException("Chat upstream must be a reviewed IPv4 loopback Python origin");if(connect<1||connect>10000||read<1||read>60000||max<4096||max>131072)throw new IllegalArgumentException("Invalid chat transport bounds");if(enabled&&!secret.matches("[A-Za-z0-9_-]{64,128}"))throw new IllegalStateException("Private chat service token is required");this.json=json.copy().enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);this.enabled=enabled;this.maxBytes=max;this.secret=secret;
  var http=HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connect)).followRedirects(HttpClient.Redirect.NEVER).proxy(new ProxySelector(){public List<Proxy> select(URI u){return List.of(Proxy.NO_PROXY);}public void connectFailed(URI u,SocketAddress a,java.io.IOException e){}}).build();var factory=new JdkClientHttpRequestFactory(http);factory.setReadTimeout(Duration.ofMillis(read));client=RestClient.builder().baseUrl(base).requestFactory(factory).build();
 }
 public JsonNode chat(JsonNode request){if(TransactionSynchronizationManager.isActualTransactionActive())throw new IllegalStateException("AI chat cannot run inside a database transaction");if(!enabled)throw new ChatFailure(503,"AI_UNAVAILABLE","AI chat is disabled or unavailable.");try{byte[] body=json.writeValueAsBytes(request);if(body.length>32768)throw new ChatFailure(422,"EVIDENCE_TOO_LARGE","Authorized chat snapshot exceeds the32KB internal request limit.");return client.post().uri("/api/v1/chat").contentType(MediaType.APPLICATION_JSON).header("X-PayMesh-AI-Chat-Token",secret).body(body).exchange((r,s)->{if(!s.getStatusCode().is2xxSuccessful())throw new ChatFailure(s.getStatusCode().value()==504?504:s.getStatusCode().value()==429||s.getStatusCode().value()==503?503:502,s.getStatusCode().value()==504?"AI_TIMEOUT":"AI_UNAVAILABLE","Private AI chat service is unavailable.");if(s.getHeaders().getContentType()==null||!MediaType.APPLICATION_JSON.isCompatibleWith(s.getHeaders().getContentType()))throw ChatResponseValidator.invalid();byte[] bytes=s.getBody().readNBytes(maxBytes+1);if(bytes.length>maxBytes)throw ChatResponseValidator.invalid();try{return json.readTree(bytes);}catch(java.io.IOException ex){throw ChatResponseValidator.invalid();}});
 }catch(ChatFailure ex){throw ex;}catch(Exception ex){for(Throwable cause=ex;cause!=null;cause=cause.getCause())if(cause instanceof java.net.http.HttpTimeoutException||cause instanceof java.net.SocketTimeoutException)throw new ChatFailure(504,"AI_TIMEOUT","AI chat timed out; no automatic retry was made.");throw new ChatFailure(503,"AI_UNAVAILABLE","Private AI chat service is unavailable.");}}
}
