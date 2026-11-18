package com.paymesh.backend.chat;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.core.JsonParser;
import com.paymesh.backend.security.accounts.*;
import com.paymesh.backend.investigation.AiRequestBudget;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
import org.springframework.transaction.annotation.*;
@RestController public class ChatController {
 private final ChatEvidenceBuilder evidence;private final AiChatClient client;private final ObjectMapper json;private final AiRequestBudget budget;
 public ChatController(ChatEvidenceBuilder evidence,AiChatClient client,ObjectMapper json,AiRequestBudget budget){this.evidence=evidence;this.client=client;this.json=json.copy().enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES).enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).disable(DeserializationFeature.ACCEPT_FLOAT_AS_INT).enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);this.budget=budget;
  var coercion=this.json.coercionConfigFor(com.fasterxml.jackson.databind.type.LogicalType.Textual);
  for(var shape:List.of(com.fasterxml.jackson.databind.cfg.CoercionInputShape.Integer,com.fasterxml.jackson.databind.cfg.CoercionInputShape.Float,com.fasterxml.jackson.databind.cfg.CoercionInputShape.Boolean))coercion.setCoercion(shape,com.fasterxml.jackson.databind.cfg.CoercionAction.Fail);
 }
 @PostMapping(value="/api/v1/merchant/ai/chat",consumes="application/json") @Transactional(propagation=Propagation.NEVER) public ResponseEntity<?> merchant(@RequestBody byte[] body,HttpServletRequest req){return process("merchant",null,body,req);}
 @PostMapping(value="/api/v1/admin/ai/chat",consumes="application/json") @Transactional(propagation=Propagation.NEVER) public ResponseEntity<?> admin(@RequestBody byte[] body,HttpServletRequest req){return process("admin",null,body,req);}
 @PostMapping(value="/api/v1/payments/{paymentId}/ai/chat",consumes="application/json") @Transactional(propagation=Propagation.NEVER) public ResponseEntity<?> payment(@PathVariable String paymentId,@RequestBody byte[] body,HttpServletRequest req){return process("payment",paymentId,body,req);}
 private ResponseEntity<?> process(String endpoint,String path,byte[] body,HttpServletRequest req){UUID correlation=UUID.randomUUID();try{if(req.getQueryString()!=null)throw ChatDtos.invalid();ChatDtos.Input input;try{input=json.readValue(body,ChatDtos.Input.class);}catch(java.io.IOException ex){throw ChatDtos.invalid();}input=ChatDtos.validate(input);UUID payment=path==null?null:ChatDtos.uuid(path);var snapshot=evidence.collect(endpoint,payment,input,correlation);ChatRules.expected(snapshot.request());if(json.writeValueAsBytes(snapshot.request()).length>32768)throw new ChatFailure(422,"EVIDENCE_TOO_LARGE","Authorized chat snapshot exceeds the32KB internal request limit.");if(!budget.acquire())throw new ChatFailure(503,"AI_CAPACITY","AI capacity is busy; try later deliberately.");try{JsonNode raw=client.chat(snapshot.request());var result=ChatResponseValidator.validate(raw,snapshot);evidence.recheck(snapshot,input,payment);return ResponseEntity.ok().cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(result);}finally{budget.release();}
 }catch(ChatFailure ex){return failure(ex,correlation.toString());}catch(AccountAccessDeniedException|org.springframework.security.access.AccessDeniedException ex){return failure(new ChatFailure(403,"ACCESS_DENIED","Access denied by current authorization."),correlation.toString());}catch(com.paymesh.backend.exception.PaymentNotFoundException ex){return failure(new ChatFailure(404,"CONTEXT_UNAVAILABLE","Selected payment is unavailable."),correlation.toString());}catch(IllegalArgumentException ex){return failure(ChatDtos.invalid(),correlation.toString());}catch(Exception ex){return failure(new ChatFailure(503,"EVIDENCE_UNAVAILABLE","Chat evidence or service is unavailable."),correlation.toString());}finally{Arrays.fill(body,(byte)0);}}
 private ResponseEntity<?> failure(ChatFailure f){return failure(f,UUID.randomUUID().toString());}
 private ResponseEntity<?> failure(ChatFailure f,String correlation){org.slf4j.LoggerFactory.getLogger(ChatController.class).warn("Chat request failed code={} correlation={} status={}",f.code(),correlation,f.status());return ResponseEntity.status(f.status()).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(Map.of("correlationId",correlation,"code",f.code(),"message",f.getMessage()));}
 @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)ResponseEntity<?> invalid(){return failure(ChatDtos.invalid());}
}
