package com.paymesh.backend.security.auth;

import com.paymesh.backend.security.accounts.*;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.core.JsonParser;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
@ConditionalOnWebApplication(type=ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/merchant/payment-links")
public class PaymentLinkController {
    private final PaymentLinks links;private final ObjectMapper json;
    public PaymentLinkController(PaymentLinks links,ObjectMapper json){this.links=links;this.json=json;}
    @ModelAttribute void multiplicity(jakarta.servlet.http.HttpServletRequest req){if(req.getQueryString()!=null&&req.getQueryString().length()>2048||req.getParameterMap().values().stream().anyMatch(v->v.length!=1))throw new IllegalArgumentException();}
    @GetMapping public ResponseEntity<?> list(@RequestParam Map<String,String> p){return safe(()->reply(200,links.list(p)));}
    @GetMapping("/{id}") public ResponseEntity<?> get(@PathVariable String id,@RequestParam Map<String,String> p){return safe(()->{empty(p);return reply(200,links.get(uuid(id)));});}
    @PostMapping(consumes="application/json") public ResponseEntity<?> create(@RequestHeader(value="Idempotency-Key",required=false) String key,@RequestBody byte[] bytes,@RequestParam Map<String,String> p){return safe(()->{
        empty(p);PaymentLinks.Input input;
        try{input=json.readerFor(PaymentLinks.Input.class).with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES).with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).without(DeserializationFeature.ACCEPT_FLOAT_AS_INT).with(JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readValue(bytes);}catch(java.io.IOException e){throw new IllegalArgumentException();}
        var r=links.create(input,key);return reply(r.replay()?200:201,r.data());
    });}
    @PostMapping("/{id}/cancel") public ResponseEntity<?> cancel(@PathVariable String id,@RequestBody(required=false) byte[] bytes,@RequestParam Map<String,String> p){return safe(()->{empty(p);if(bytes!=null&&bytes.length>0)throw new IllegalArgumentException();return reply(200,links.cancel(uuid(id)));});}
    private void empty(Map<String,String> p){if(!p.isEmpty())throw new IllegalArgumentException();}
    private UUID uuid(String s){UUID id=UUID.fromString(s);if(!id.toString().equals(s))throw new IllegalArgumentException();return id;}
    private ResponseEntity<?> reply(int code,Object body){return ResponseEntity.status(code).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(body);}
    private ResponseEntity<?> safe(Supplier<ResponseEntity<?>> action){try{return action.get();}catch(IllegalArgumentException e){return reply(400,Map.of("message","Invalid payment link request."));}catch(AccountAccessDeniedException e){return reply(403,Map.of("message","Access denied."));}catch(PaymentLinks.Missing e){return reply(404,Map.of("message","Payment link unavailable."));}catch(PaymentLinks.Conflict e){return reply(409,Map.of("message","Payment link conflict. Refresh authoritative state."));}catch(RuntimeException e){return reply(503,Map.of("message","Outcome unconfirmed. Do not automatically retry."));}}
    @ExceptionHandler({org.springframework.http.converter.HttpMessageNotReadableException.class,IllegalArgumentException.class}) ResponseEntity<?> invalid(){return reply(400,Map.of("message","Invalid payment link request."));}
}
