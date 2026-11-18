package com.paymesh.backend.security.auth;
import com.paymesh.backend.security.accounts.CheckoutTransactions;
import com.paymesh.backend.service.impl.CheckoutExecution;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.core.JsonParser;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.core.env.Environment;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
@RestController
@ConditionalOnWebApplication(type=ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/checkout")
public class CheckoutController {
 private final CheckoutTransactions transactions;private final CheckoutExecution execution;private final CheckoutRateLimit limits;private final ObjectMapper json;private final String origin;
 public CheckoutController(CheckoutTransactions transactions,CheckoutExecution execution,CheckoutRateLimit limits,ObjectMapper json,Environment env){this.transactions=transactions;this.execution=execution;this.limits=limits;this.json=json;origin=env.getProperty("paymesh.sessions.origin","http://127.0.0.1:5500");}
 @GetMapping({"/{token}","/{token}/status"}) public ResponseEntity<?> read(@PathVariable String token,HttpServletRequest req){return safe(token,req,false,()->reply(200,transactions.read(token)));}
 @PostMapping(value="/{token}/pay",consumes="application/json") public ResponseEntity<?> pay(@PathVariable String token,@RequestHeader(value="Idempotency-Key",required=false) String key,@RequestBody byte[] body,HttpServletRequest req){return safe(token,req,true,()->{
  JsonNode data;try{data=json.readerFor(JsonNode.class).with(JsonParser.Feature.STRICT_DUPLICATE_DETECTION).with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).readValue(body);}catch(java.io.IOException ex){throw new IllegalArgumentException();}
  if(data==null||!data.isObject()||!data.has("confirmed")||!data.get("confirmed").isBoolean()||!data.get("confirmed").booleanValue())throw new IllegalArgumentException();
  var keys=new HashSet<String>();data.fieldNames().forEachRemaining(keys::add);if(!Set.of("confirmed","simulationOutcome").containsAll(keys)||data.has("simulationOutcome")&&!data.get("simulationOutcome").isTextual())throw new IllegalArgumentException();
  var result=execution.pay(token,key,data.has("simulationOutcome")?data.get("simulationOutcome").textValue():null);return reply(Set.of("PROCESSING","UNCERTAIN").contains(result.get("checkoutStatus"))?202:200,result);
 });}
 private ResponseEntity<?> safe(String token,HttpServletRequest req,boolean post,Supplier<ResponseEntity<?>> action){try{
  CheckoutTransactions.token(token);if(req.getQueryString()!=null||req.getRequestURI().length()>256)throw new IllegalArgumentException();
  String supplied=req.getHeader("Origin");if(supplied!=null&&!Collections.list(req.getHeaders("Origin")).equals(List.of(origin)))return reply(403,Map.of("message","Checkout request denied."));if("cross-site".equals(req.getHeader("Sec-Fetch-Site"))||supplied!=null&&!origin.equals(supplied)||post&&(!origin.equals(supplied)||!"1".equals(req.getHeader("X-PayMesh-Checkout"))))return reply(403,Map.of("message","Checkout request denied."));
  if(!limits.allow(req.getRemoteAddr(),token,post))return ResponseEntity.status(429).header("Retry-After","60").cacheControl(CacheControl.noStore()).body(Map.of("message","Wait before another checkout request."));return action.get();
 }catch(IllegalArgumentException ex){return reply(400,Map.of("message","Invalid checkout request."));}catch(CheckoutTransactions.Missing ex){return reply(404,Map.of("message","Checkout unavailable."));}catch(CheckoutTransactions.Conflict ex){return reply(409,Map.of("message","Refresh checkout status before another action."));}catch(RuntimeException ex){return reply(503,Map.of("message","Checkout outcome unconfirmed. Check status; do not retry automatically."));}}
 private ResponseEntity<?> reply(int status,Object data){return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).header("Referrer-Policy","no-referrer").header("X-Content-Type-Options","nosniff").body(data);}
 @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class) ResponseEntity<?> invalid(){return reply(400,Map.of("message","Invalid checkout request."));}
}
