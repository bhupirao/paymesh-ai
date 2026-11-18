package com.paymesh.backend.chat;
import java.util.*;
public final class ChatDtos {
 private ChatDtos(){}
 public record Message(String role,String content){}
 public record Statistics(String from,String to,String currency){}
 public record Context(String paymentId,String paymentLinkId,String merchantId,Statistics statistics){}
 public record Input(String question,List<Message> history,Context context){@Override public String toString(){return "Chat input [redacted]";}}
 public record Reference(String reference,String resourceType,String resourceId){}
 public record Knowledge(String documentId,String chunkId,String title,List<String> sources,double score){}
 public record Money(String kind,String amount,String currency,Long count){}
 public record Provenance(String source,String collectedAt,String scope,List<String> limitations,Map<String,Object> statisticsRange){}
 public record Response(String correlationId,String answer,String intent,Provenance evidenceProvenance,List<Reference> evidenceReferences,List<Knowledge> knowledgeReferences,List<String> limitations,List<String> suggestedFollowUps,List<Money> moneyFacts,String analysisMode,String generationStatus){@Override public String toString(){return "Chat response [redacted]";}}
 public static Input validate(Input input){
  if(input==null)throw invalid();text(input.question(),1000);List<Message> history=input.history()==null?List.of():input.history();if(history.size()>8)throw invalid();int total=0;
  for(var m:history){if(m==null||m.role()==null||!Set.of("user","assistant").contains(m.role()))throw invalid();text(m.content(),1000);total+=m.content().codePointCount(0,m.content().length());}if(total>6000)throw invalid();
  var c=input.context();if(c!=null){if(c.paymentId()!=null)uuid(c.paymentId());if(c.paymentLinkId()!=null)uuid(c.paymentLinkId());if(c.paymentId()!=null&&c.paymentLinkId()!=null)throw invalid();if(c.merchantId()!=null&&!c.merchantId().matches("[A-Za-z0-9][A-Za-z0-9._:-]{0,99}"))throw invalid();if(c.statistics()!=null){var s=c.statistics();if(s.from()!=null&&s.from().length()>35||s.to()!=null&&s.to().length()>35||s.currency()!=null&&!Set.of("INR","USD").contains(s.currency()))throw invalid();}}
  return new Input(input.question(),List.copyOf(history),c);
 }
 public static UUID uuid(String value){try{var id=UUID.fromString(value);if(!id.toString().equals(value))throw invalid();return id;}catch(RuntimeException ex){throw invalid();}}
 private static void text(String s,int max){if(s==null||s.isBlank()||s.codePointCount(0,s.length())>max)throw invalid();for(int i=0;i<s.length();i++){char c=s.charAt(i);if(c==0||c==127||c<32&&c!='\n'&&c!='\t')throw invalid();if(Character.isSurrogate(c)){if(!Character.isHighSurrogate(c)||i+1>=s.length()||!Character.isLowSurrogate(s.charAt(++i)))throw invalid();}}
  // Not a universal secret detector. Reject common accidental credentials/contacts/IDs;
  // no arbitrary resource identifier in text can become a selector.
  if(java.util.regex.Pattern.compile("(?i)eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}|\\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\\b|\\b[A-Za-z0-9_-]{43,}\\b|\\b[0-9][0-9 ()+-]{8,}[0-9]\\b|\\b(password|secret|authorization|cookie|refresh.?token|api.?key|cvv|pin)\\s*[:=]\\s*\\S+").matcher(s).find())throw new ChatFailure(400,"SENSITIVE_TEXT","Remove credentials, contact details and identifiers from chat text; use authorized selectors.");
 }
 public static ChatFailure invalid(){return new ChatFailure(400,"INVALID_INPUT","Invalid chat request or unsupported context selector.");}
}
