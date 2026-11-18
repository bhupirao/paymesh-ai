package com.paymesh.backend.chat;
import com.fasterxml.jackson.databind.*;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
class AiChatClientTest {
 HttpServer server;int port;String body="{\"ok\":true}";int status=200;String type="application/json";CountDownLatch hold;AtomicInteger calls=new AtomicInteger();AtomicReference<com.sun.net.httpserver.Headers> headers=new AtomicReference<>();
 @BeforeEach void setup()throws Exception{server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);port=server.getAddress().getPort();server.createContext("/api/v1/chat",e->{calls.incrementAndGet();headers.set(e.getRequestHeaders());assertEquals("POST",e.getRequestMethod());e.getRequestBody().readAllBytes();try{if(hold!=null)hold.await(2,TimeUnit.SECONDS);}catch(InterruptedException ex){Thread.currentThread().interrupt();}byte[] b=body.getBytes(StandardCharsets.UTF_8);e.getResponseHeaders().set("Content-Type",type);if(status==302)e.getResponseHeaders().set("Location","http://127.0.0.1:"+port+"/must-not-follow");try{e.sendResponseHeaders(status,b.length);e.getResponseBody().write(b);}finally{e.close();}});server.start();}
 @AfterEach void stop(){if(hold!=null)hold.countDown();server.stop(0);}
 AiChatClient client(int timeout){return new AiChatClient(new ObjectMapper(),true,"http://127.0.0.1:"+port,1000,timeout,4096,"T".repeat(64));}
 @Test void fixedPathAndServiceCredentialOnly(){var n=client(1000).chat(new ObjectMapper().createObjectNode().put("question","synthetic"));assertTrue(n.path("ok").asBoolean());assertEquals("T".repeat(64),headers.get().getFirst("X-PayMesh-AI-Chat-Token"));assertNull(headers.get().getFirst("Authorization"));assertNull(headers.get().getFirst("Cookie"));}
 @Test void redirectsAndMalformedResponsesRejected(){status=302;assertEquals(502,assertThrows(ChatFailure.class,()->client(1000).chat(new ObjectMapper().createObjectNode())).status());assertEquals(1,calls.get());status=200;body="{\"a\":1,\"a\":2}";assertEquals(502,assertThrows(ChatFailure.class,()->client(1000).chat(new ObjectMapper().createObjectNode())).status());}
 @Test void boundedUtf8RequestAndResponse(){var request=new ObjectMapper().createObjectNode().put("q","😀".repeat(10000));assertEquals(422,assertThrows(ChatFailure.class,()->client(1000).chat(request)).status());assertEquals(0,calls.get());body="x".repeat(4097);assertEquals(502,assertThrows(ChatFailure.class,()->client(1000).chat(new ObjectMapper().createObjectNode())).status());}
 @Test void timeoutIsDistinct(){hold=new CountDownLatch(1);assertEquals(504,assertThrows(ChatFailure.class,()->client(20).chat(new ObjectMapper().createObjectNode())).status());hold.countDown();}
 @Test void transportRejectsTransactions(){org.springframework.transaction.support.TransactionSynchronizationManager.setActualTransactionActive(true);try{assertThrows(IllegalStateException.class,()->client(1000).chat(new ObjectMapper().createObjectNode()));assertEquals(0,calls.get());}finally{org.springframework.transaction.support.TransactionSynchronizationManager.setActualTransactionActive(false);}}
 @Test void configurationFailsClosed(){for(String base:new String[]{"http://example.test:8000","http://127.0.0.1:8080","http://127.0.0.1:8000/path","http://user:pass@127.0.0.1:8000"})assertThrows(IllegalArgumentException.class,()->new AiChatClient(new ObjectMapper(),true,base,1000,1000,4096,"T".repeat(64)));assertThrows(IllegalStateException.class,()->new AiChatClient(new ObjectMapper(),true,"http://127.0.0.1:8000",1000,1000,4096,""));}
}
