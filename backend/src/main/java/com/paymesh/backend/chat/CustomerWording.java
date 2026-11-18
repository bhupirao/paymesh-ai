package com.paymesh.backend.chat;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.*;
/** Wording only. Uses existing validated money facts without recalculation. */
final class CustomerWording {
 private static JsonNode config(){return ChatRules.CONTRACT.path("customerWording");}
 private static String text(String key,String... values){String out=config().path("words").path(key).asText();for(int i=0;i<values.length;i+=2)out=out.replace("{"+values[i]+"}",values[i+1]);return out;}
 private static String amount(JsonNode f){return (f.path("currency").asText().equals("USD")?"$":"₹")+f.path("amount").asText();}
 static String render(JsonNode req,ChatRules.Expected raw){
  String intent=raw.intent();JsonNode e=req.path("evidence"),p=e.path("payment");Map<String,JsonNode> facts=new HashMap<>();raw.money().forEach(f->facts.put(f.path("kind").asText(),f));
  if(intent.equals("UNSUPPORTED"))return text("unsupported");if(intent.equals("INSUFFICIENT_EVIDENCE"))return text("clarify");if(intent.equals("KNOWLEDGE"))return ChatRules.CONTRACT.path("policies").path(raw.topic()).get(3).asText();
  if(intent.equals("CHECKOUT")){var c=e.path("checkout");if(!c.isObject())return text("checkout_missing");String state=c.path("status").asText();return text("checkout","status",config().path("status").path(state).asText(),"detail",config().path("checkoutDetails").path(state).asText());}
  if(intent.equals("STATISTICS")){if(!e.path("statistics").isArray())return text("statistics_missing");List<String> lines=new ArrayList<>();raw.money().forEach(f->lines.add(f.path("currency").asText()+" "+(f.path("kind").asText().equals("PAYMENT_AGGREGATE")?"payments":"refunds")+": "+f.path("count").asText()+", totalling "+amount(f)));return text(e.path("statisticsComplete").asBoolean()?"statistics_complete":"statistics_incomplete","summary",lines.isEmpty()?"no complete totals are available":String.join("; ",lines));}
  if(!p.isObject())return text("missing_payment");String state=p.path("status").asText(),status=config().path("status").path(state).asText();
  if(intent.equals("REFUND_SUMMARY")){var total=facts.get("OBSERVED_SUCCESSFUL_REFUNDS");var remaining=facts.get("REMAINING_REFUNDABLE");if(total==null)return text("refund_unavailable");if(!e.path("refundHistoryComplete").asBoolean())return text("refund_partial_history","refunded",amount(total));if(remaining==null)return text("refund_ineligible","refunded",amount(total));if(remaining.path("amount").asText().equals("0.00"))return text("refund_full","refunded",amount(total));return text(total.path("amount").asText().equals("0.00")?"refund_none":"refund_some","refunded",amount(total),"remaining",amount(remaining));}
  if(intent.equals("GATEWAY")){var gs=e.path("gateways");if(!gs.isArray())return text("gateway_missing");if(gs.isEmpty())return text("gateway_empty");Map<String,String> labels=Map.of("MOCK_RAZORPAY","Simulated Razorpay","MOCK_STRIPE","Simulated Stripe","MOCK_ROUTER","Simulated routing");List<String> lines=new ArrayList<>();gs.forEach(g->lines.add(labels.get(g.path("gatewayName").asText())+" — "+g.path("status").asText().toLowerCase(Locale.ROOT)));return text("gateway_records","observations",String.join(", ",lines));}
  if(intent.equals("PAYMENT_FAILURE"))return state.equals("FAILED")?text("failure"):text("not_failure","status",status);
  if(intent.equals("PROCESSING"))return state.equals("PROCESSING")?text("processing"):text("not_processing","status",status);
  return text("status","status",status,"detail",config().path("statusDetails").path(state).asText());
 }
}
