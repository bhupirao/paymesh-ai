package com.paymesh.backend.chat.conversations;
import com.paymesh.backend.chat.*;
import com.paymesh.backend.security.accounts.AccountAccessDeniedException;
import com.paymesh.backend.exception.PaymentNotFoundException;
import com.fasterxml.jackson.databind.*;
import com.fasterxml.jackson.core.JsonParser;
import jakarta.servlet.http.HttpServletRequest;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.*;
@RestController
@RequestMapping("/api/v1/{portal:merchant|admin}/ai/conversations")
public class ConversationController {
 private final ConversationTransactions store;private final ConversationService service;private final ObjectMapper json;
 public ConversationController(ConversationTransactions store,ConversationService service,ObjectMapper json){this.store=store;this.service=service;this.json=json.copy().enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES).enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).disable(DeserializationFeature.ACCEPT_FLOAT_AS_INT).enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);for(var shape:List.of(com.fasterxml.jackson.databind.cfg.CoercionInputShape.Integer,com.fasterxml.jackson.databind.cfg.CoercionInputShape.Float,com.fasterxml.jackson.databind.cfg.CoercionInputShape.Boolean))this.json.coercionConfigFor(com.fasterxml.jackson.databind.type.LogicalType.Textual).setCoercion(shape,com.fasterxml.jackson.databind.cfg.CoercionAction.Fail);this.json.coercionConfigFor(com.fasterxml.jackson.databind.type.LogicalType.Integer).setCoercion(com.fasterxml.jackson.databind.cfg.CoercionInputShape.String,com.fasterxml.jackson.databind.cfg.CoercionAction.Fail);}

 private <T>T parse(byte[] body,Class<T> type){try{if(body.length>8192)throw new ChatFailure(413,"REQUEST_TOO_LARGE","Conversation request exceeds 8 KiB.");T value=json.readValue(body,type);if(value==null)throw ChatDtos.invalid();return value;}catch(ChatFailure e){throw e;}catch(Exception e){throw ChatDtos.invalid();}}
 private UUID id(String value){return ChatDtos.uuid(value);}
 private ResponseEntity<?> run(Supplier<Map<String,Object>> work,byte[] body,HttpServletRequest req,Set<String> keys){try{for(var entry:req.getParameterMap().entrySet())if(!keys.contains(entry.getKey())||entry.getValue().length!=1)throw ChatDtos.invalid();if(body!=null&&req.getQueryString()!=null)throw ChatDtos.invalid();var result=work.get();int status="IN_PROGRESS".equals(result.get("status"))||"UNCERTAIN".equals(result.get("status"))?202:result.containsKey("replay")&&Boolean.FALSE.equals(result.get("replay"))?201:200;return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(result);
 }catch(ChatFailure e){return error(e.status(),e.code(),e.getMessage());}catch(AccountAccessDeniedException|org.springframework.security.access.AccessDeniedException e){return error(403,"ACCESS_DENIED","Current conversation authorization is unavailable.");}catch(PaymentNotFoundException e){return error(404,"CONVERSATION_UNAVAILABLE","Conversation is unavailable.");}catch(IllegalArgumentException e){return error(400,"INVALID_INPUT","Invalid conversation input or context.");}catch(Exception e){return error(503,"CONVERSATION_UNAVAILABLE","Conversation outcome is unavailable. Reconcile authorized state before retrying.");}finally{if(body!=null)Arrays.fill(body,(byte)0);}}
 private ResponseEntity<?> error(int status,String code,String text){return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(Map.of("code",code,"message",text,"correlationId",UUID.randomUUID().toString()));}
 private int number(Map<String,String> q,String key,int fallback){return q.containsKey(key)?Integer.parseInt(q.get(key)):fallback;}
 @PostMapping(consumes="application/json") public ResponseEntity<?> create(@PathVariable String portal,@RequestBody byte[] body,HttpServletRequest r){return run(()->store.create(portal,parse(body,ConversationDtos.Create.class)),body,r,Set.of());}
 @GetMapping public ResponseEntity<?> list(@PathVariable String portal,@RequestParam Map<String,String> q,HttpServletRequest r){return run(()->store.list(portal,number(q,"page",0),number(q,"size",5),q.getOrDefault("search",""),q.containsKey("paymentId")?id(q.get("paymentId")):null),null,r,Set.of("page","size","search","paymentId"));}
 @GetMapping("/creations/{requestId}") public ResponseEntity<?> creation(@PathVariable String portal,@PathVariable String requestId,HttpServletRequest r){return run(()->store.creation(portal,id(requestId)),null,r,Set.of());}
 @GetMapping("/{conversationId}") public ResponseEntity<?> detail(@PathVariable String portal,@PathVariable String conversationId,HttpServletRequest r){return run(()->store.detail(portal,id(conversationId)),null,r,Set.of());}
 @GetMapping("/{conversationId}/messages") public ResponseEntity<?> messages(@PathVariable String portal,@PathVariable String conversationId,@RequestParam Map<String,String> q,HttpServletRequest r){return run(()->store.messages(portal,id(conversationId),number(q,"page",0),number(q,"size",5)),null,r,Set.of("page","size"));}
 @GetMapping("/{conversationId}/requests/{requestId}") public ResponseEntity<?> status(@PathVariable String portal,@PathVariable String conversationId,@PathVariable String requestId,HttpServletRequest r){return run(()->store.requestStatus(portal,id(conversationId),id(requestId)),null,r,Set.of());}
 @PostMapping(value="/{conversationId}/messages",consumes="application/json") public ResponseEntity<?> send(@PathVariable String portal,@PathVariable String conversationId,@RequestBody byte[] body,HttpServletRequest r){return run(()->service.send(portal,id(conversationId),parse(body,ConversationDtos.Send.class)),body,r,Set.of());}
 @PostMapping(value="/{conversationId}/rename",consumes="application/json") public ResponseEntity<?> rename(@PathVariable String portal,@PathVariable String conversationId,@RequestBody byte[] body,HttpServletRequest r){return run(()->store.rename(portal,id(conversationId),parse(body,ConversationDtos.Rename.class)),body,r,Set.of());}
 @PostMapping(value="/{conversationId}/delete",consumes="application/json") public ResponseEntity<?> delete(@PathVariable String portal,@PathVariable String conversationId,@RequestBody byte[] body,HttpServletRequest r){return run(()->store.delete(portal,id(conversationId),ConversationDtos.version(parse(body,ConversationDtos.Version.class).expectedVersion())),body,r,Set.of());}
 @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class) public ResponseEntity<?> unreadable(){return error(400,"INVALID_INPUT","Invalid conversation request.");}
}
