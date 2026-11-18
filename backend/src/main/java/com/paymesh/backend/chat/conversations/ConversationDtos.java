package com.paymesh.backend.chat.conversations;
import com.paymesh.backend.chat.*;
import java.util.*;
public final class ConversationDtos {
 private ConversationDtos(){}
 public record Create(String requestId,ChatDtos.Context context,String title){}
 public record Send(String requestId,Long expectedVersion,String question){@Override public String toString(){return "Conversation request [redacted]";}}
 public record Rename(Long expectedVersion,String title){}
 public record Version(Long expectedVersion){}
 public record Turn(String requestId,int turnIndex,String question,ChatDtos.Response response,String createdAt){}
 public record Work(UUID conversationId,UUID requestId,UUID nonce,long expectedVersion,String question,ChatDtos.Input input,UUID actor,long authorizationVersion,String merchantId,Map<String,Object> immediate){@Override public String toString(){return "Conversation work [redacted]";}}
 public static String title(String value){if(value==null||value.isBlank()||value.codePointCount(0,value.length())>120||value.chars().anyMatch(c->c<32||c==127)||!java.nio.charset.StandardCharsets.UTF_8.newEncoder().canEncode(value))throw ChatDtos.invalid();ChatDtos.validate(new ChatDtos.Input(value,List.of(),null));return value.strip();}
 public static long version(Long value){if(value==null||value<0)throw ChatDtos.invalid();return value;}
 public static ChatFailure missing(){return new ChatFailure(404,"CONVERSATION_UNAVAILABLE","Conversation is unavailable.");}
 public static ChatFailure conflict(){return new ChatFailure(409,"CONVERSATION_CONFLICT","Conversation or request changed. Reconcile authorized state before retrying.");}
}
