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
@RequestMapping("/api/v1/merchant")
public class MerchantPortalController {
    private final MerchantPortal portal;private final ObjectMapper json;
    public MerchantPortalController(MerchantPortal portal,ObjectMapper json){this.portal=portal;this.json=json;}
    @ModelAttribute public void queryMultiplicity(jakarta.servlet.http.HttpServletRequest request){if(request.getParameterMap().values().stream().anyMatch(v->v.length!=1))throw new IllegalArgumentException("Duplicate query parameters");}
    @GetMapping("/analytics") public ResponseEntity<?> analytics(@RequestParam Map<String,String> p){return safely(()->portal.analytics(p));}
    @GetMapping("/dashboard") public ResponseEntity<?> dashboard(@RequestParam Map<String,String> p){return safely(()->portal.dashboard(query(p,"dashboard")));}
    @GetMapping("/payments") public ResponseEntity<?> payments(@RequestParam Map<String,String> p){return safely(()->portal.financial("payments",query(p,"payments")));}
    @GetMapping("/refunds") public ResponseEntity<?> refunds(@RequestParam Map<String,String> p){return safely(()->portal.financial("refunds",query(p,"refunds")));}
    @GetMapping("/profile") public ResponseEntity<?> profile(@RequestParam Map<String,String> p){return safely(()->{if(!p.isEmpty())throw new IllegalArgumentException();return portal.profile();});}
    @PostMapping(value="/profile/password",consumes=MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> password(@RequestBody byte[] body){
        Password input=null;
        try{input=read(body,Password.class);Password values=input;return safely(()->{portal.changePassword(values.currentPassword,values.newPassword,values.confirmPassword);return Map.of("message","Password changed. Sign in again; prior sessions are revoked.");});}
        catch(IllegalArgumentException ex){return reply(400,Map.of("message","Invalid password request."));}
        finally{Arrays.fill(body,(byte)0);if(input!=null)for(char[] value:new char[][]{input.currentPassword,input.newPassword,input.confirmPassword})if(value!=null)Arrays.fill(value,'\0');}
    }
    private AdminQueries.Query query(Map<String,String> p,String kind){
        Set<String> allowed=kind.equals("dashboard")?Set.of("currency","from","to"):Set.of("page","size","search","status","currency","sort","from","to");
        if(!allowed.containsAll(p.keySet()))throw new IllegalArgumentException();
        var q=AdminQueries.Query.parse(p);
        if(!q.status().isEmpty()&&!(kind.equals("refunds")?Set.of("SUCCESS"):Set.of("CREATED","PROCESSING","SUCCESS","FAILED","CANCELLED","REFUNDED")).contains(q.status()))throw new IllegalArgumentException();return q;
    }
    private <T>T read(byte[] body,Class<T> type){try{T value=json.readerFor(type).with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES).with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).with(JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readValue(body);if(value==null)throw new IllegalArgumentException();return value;}catch(java.io.IOException ex){throw new IllegalArgumentException();}}
    private UUID uuid(String value){UUID id=UUID.fromString(value);if(!id.toString().equalsIgnoreCase(value))throw new IllegalArgumentException();return id;}
    private ResponseEntity<?> safely(Supplier<?> action){try{return reply(200,action.get());}catch(IllegalArgumentException ex){return reply(400,Map.of("message","Check filters, fields and password requirements."));}catch(AccountAccessDeniedException ex){return reply(403,Map.of("message","Access denied. Check current authorization or current password."));}catch(MerchantAdministration.Missing ex){return reply(404,Map.of("message","Requested record is unavailable."));}catch(MerchantAdministration.Conflict ex){return reply(409,Map.of("message","Refresh authorized state before another action."));}catch(RuntimeException ex){return reply(503,Map.of("message","Operation could not be confirmed. Refresh authoritative state before considering another action."));}}
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
