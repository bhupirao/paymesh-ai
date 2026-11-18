package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.*;
import com.paymesh.backend.security.accounts.*;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
@ConditionalOnWebApplication(type=ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/admin")
public class AdminManagementController {
    private final AdminQueries queries;private final MerchantAdministration administration;private final ObjectMapper json;
    public AdminManagementController(AdminQueries queries,MerchantAdministration administration,ObjectMapper json){this.queries=queries;this.administration=administration;this.json=json;}
    @ModelAttribute public void queryMultiplicity(jakarta.servlet.http.HttpServletRequest request){if(request.getParameterMap().values().stream().anyMatch(v->v.length!=1))throw new IllegalArgumentException("Duplicate query parameters");}
    @GetMapping("/analytics") public ResponseEntity<?> analytics(@RequestParam Map<String,String> p){return safely(()->queries.analytics(p));}
    @GetMapping("/dashboard") public ResponseEntity<?> dashboard(@RequestParam Map<String,String> p){return safely(()->queries.dashboard(query(p,"dashboard")));}
    @GetMapping("/merchants") public ResponseEntity<?> merchants(@RequestParam Map<String,String> p){return safely(()->queries.merchants(query(p,"merchants")));}
    @GetMapping("/merchant") public ResponseEntity<?> merchant(@RequestParam Map<String,String> p){return safely(()->{if(!p.keySet().equals(Set.of("merchantId")))throw new IllegalArgumentException();return queries.merchant(p.get("merchantId"));});}
    @GetMapping("/payments") public ResponseEntity<?> payments(@RequestParam Map<String,String> p){return safely(()->queries.financial("payments",query(p,"payments")));}
    @GetMapping("/refunds") public ResponseEntity<?> refunds(@RequestParam Map<String,String> p){return safely(()->queries.financial("refunds",query(p,"refunds")));}
    @GetMapping("/payments/{id}") public ResponseEntity<?> payment(@PathVariable String id){return safely(()->queries.financialDetail("payments",uuid(id)));}
    @GetMapping("/refunds/{id}") public ResponseEntity<?> refund(@PathVariable String id){return safely(()->queries.financialDetail("refunds",uuid(id)));}
    @GetMapping("/audit") public ResponseEntity<?> audit(@RequestParam Map<String,String> p){return safely(()->queries.audit(query(p,"audit")));}
    @GetMapping("/accounts") public ResponseEntity<?> accounts(@RequestParam Map<String,String> p){return safely(()->queries.accounts(query(p,"accounts")));}
    @GetMapping("/profile") public ResponseEntity<?> profile(){return safely(queries::profile);}
    @PostMapping(value="/merchant/approve",consumes=MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> approve(@RequestBody byte[] body){return safely(()->{Approve input=read(body,Approve.class);return administration.transition(input.merchantId,"approve",null,input.reviewReference,Boolean.TRUE.equals(input.ownershipAttested));});}
    @PostMapping(value="/merchant/{action:reject|suspend|reactivate}",consumes=MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> action(@PathVariable String action,@RequestBody byte[] body){return safely(()->{Reason input=read(body,Reason.class);return administration.transition(input.merchantId,action,input.reason,null,false);});}
    @PostMapping(value="/profile/password",consumes=MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> password(@RequestBody byte[] body){
        Password input=null;
        try{input=read(body,Password.class);Password values=input;return safely(()->{administration.changePassword(values.currentPassword,values.newPassword,values.confirmPassword);return Map.of("message","Password changed. Sign in again; prior sessions are revoked.");});}
        catch(IllegalArgumentException ex){return reply(400,Map.of("message","Invalid password request."));}
        finally{Arrays.fill(body,(byte)0);if(input!=null){for(char[] value:new char[][]{input.currentPassword,input.newPassword,input.confirmPassword})if(value!=null)Arrays.fill(value,'\0');}}
    }
    private AdminQueries.Query query(Map<String,String> p,String kind){
        Set<String> common=Set.of("page","size","search","status","currency","merchantId","sort","from","to");
        Set<String> allowed=switch(kind){
            case "merchants" -> Set.of("page","size","search","status","merchantId","sort","from","to");
            case "audit" -> Set.of("page","size","search","merchantId","sort","from","to");
            case "accounts" -> Set.of("page","size","search","sort");
            case "dashboard" -> Set.of("search","status","currency","merchantId","from","to");
            default -> common;
        };
        if(!allowed.containsAll(p.keySet()))throw new IllegalArgumentException();
        var q=AdminQueries.Query.parse(p);
        if(!q.status().isEmpty()&&kind.equals("refunds")&&!q.status().equals("SUCCESS"))throw new IllegalArgumentException();
        if(!q.status().isEmpty()&&(kind.equals("payments")||kind.equals("dashboard"))&&!Set.of("CREATED","PROCESSING","SUCCESS","FAILED","CANCELLED","REFUNDED").contains(q.status()))throw new IllegalArgumentException();
        return q;
    }
    private <T>T read(byte[] body,Class<T> type){try{T value=json.readerFor(type).with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES).with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).with(JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readValue(body);if(value==null)throw new IllegalArgumentException();return value;}catch(java.io.IOException ex){throw new IllegalArgumentException();}}
    private UUID uuid(String value){UUID id=UUID.fromString(value);if(!id.toString().equalsIgnoreCase(value))throw new IllegalArgumentException();return id;}
    private ResponseEntity<?> safely(Supplier<?> action){try{return reply(200,action.get());}catch(IllegalArgumentException ex){return reply(400,Map.of("message","Check filters, fields and password requirements."));}catch(AccountAccessDeniedException ex){return reply(403,Map.of("message","Access denied. Check current authorization or current password."));}catch(MerchantAdministration.Missing ex){return reply(404,Map.of("message","Requested record is unavailable."));}catch(MerchantAdministration.Conflict ex){return reply(409,Map.of("message","State changed, transition is not eligible or ownership needs review. Refresh before another action."));}catch(RuntimeException ex){return reply(503,Map.of("message","Operation could not be confirmed. Refresh authoritative state before considering another action."));}}
    private ResponseEntity<?> reply(int status,Object body){return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(body);}
    @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class) ResponseEntity<?> invalid(){return reply(400,Map.of("message","Invalid JSON request."));}
    public static class Approve{public String merchantId;public String reviewReference;public Boolean ownershipAttested;}
    public static class Reason{public String merchantId;public String reason;}
    public static class Password{
        @com.fasterxml.jackson.annotation.JsonProperty(access=com.fasterxml.jackson.annotation.JsonProperty.Access.WRITE_ONLY)public char[] currentPassword;
        @com.fasterxml.jackson.annotation.JsonProperty(access=com.fasterxml.jackson.annotation.JsonProperty.Access.WRITE_ONLY)public char[] newPassword;
        @com.fasterxml.jackson.annotation.JsonProperty(access=com.fasterxml.jackson.annotation.JsonProperty.Access.WRITE_ONLY)public char[] confirmPassword;
    }
}
