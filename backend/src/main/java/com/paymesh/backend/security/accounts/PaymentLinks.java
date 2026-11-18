package com.paymesh.backend.security.accounts;

import java.math.*;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** No checkout execution, public token resolution or financial payment mutation. */
@Service
public class PaymentLinks {
    private final MerchantPortal portal;private final AuthStore store;private final AccountAudit audit;private final com.paymesh.backend.gateway.GatewayRouter gateways;
    public PaymentLinks(MerchantPortal portal,AuthStore store,AccountAudit audit,com.paymesh.backend.gateway.GatewayRouter gateways){this.portal=portal;this.store=store;this.audit=audit;this.gateways=gateways;}
    public record Input(String amount,String currency,String paymentMethod,String customerReference,String description,Integer expiryHours){}
    public record Result(Map<String,Object> data,boolean replay){}
    public static class Conflict extends RuntimeException{}
    public static class Missing extends RuntimeException{}
    static String text(String value,int max){if(value==null||!value.equals(value.strip())||value.length()>max||value.codePoints().anyMatch(c->Character.isISOControl(c)||c>=0xD800&&c<=0xDFFF))throw new IllegalArgumentException();return value;}
    public static Input validate(Input r){
        if(r==null||r.amount()==null||!r.amount().matches("(0|[1-9][0-9]{0,11})(\\.[0-9]{1,2})?"))throw new IllegalArgumentException();
        BigDecimal amount=new BigDecimal(r.amount()).setScale(2,RoundingMode.UNNECESSARY);if(amount.signum()<=0)throw new IllegalArgumentException();
        if(!Set.of("INR","USD").contains(r.currency()==null?"":r.currency())||!Set.of("UPI","CARD").contains(r.paymentMethod()==null?"":r.paymentMethod())||r.currency().equals("USD")&&!r.paymentMethod().equals("CARD"))throw new IllegalArgumentException();
        if(r.expiryHours()==null||!Set.of(1,24,168).contains(r.expiryHours()))throw new IllegalArgumentException();
        return new Input(amount.toPlainString(),r.currency(),r.paymentMethod(),text(r.customerReference(),100),text(r.description(),500),r.expiryHours());
    }
    static String fingerprint(Input r){return AuthStore.digest(String.join("\u0000",r.amount(),r.currency(),r.paymentMethod(),r.customerReference(),r.description(),r.expiryHours().toString()));}
    private Instant now(){return store.jdbc.queryForObject("SELECT clock_timestamp()",java.sql.Timestamp.class).toInstant();}
    private Map<String,Object> render(Map<String,Object> row,Instant now,boolean token){
        Map<String,Object> out=new LinkedHashMap<>();
        for(String[] pair:new String[][]{{"link_id","linkId"},{"merchant_id","merchantId"},{"currency","currency"},{"payment_method","paymentMethod"},{"gateway_name","gatewayName"},{"customer_reference","customerReference"},{"description","description"}})out.put(pair[1],row.get(pair[0]).toString());
        out.put("amount",((BigDecimal)row.get("amount")).toPlainString());String status=row.get("status").toString();
        var history=store.jdbc.queryForList("SELECT status FROM "+store.table("checkout_attempts")+" WHERE link_id=? ORDER BY created_at DESC,attempt_id DESC",row.get("link_id"));
        String attempt=history.stream().filter(a->!a.get("status").equals("FAILED")).map(a->a.get("status").toString()).findFirst().orElse(history.isEmpty()?null:history.getFirst().get("status").toString());
        if(status.equals("ACTIVE")&&Set.of("PROCESSING","UNCERTAIN").contains(attempt==null?"":attempt))status="PROCESSING";
        if(status.equals("ACTIVE")&&!AuthStore.instant(row,"expires_at").isAfter(now))status="EXPIRED";
        out.put("checkoutAttemptStatus",attempt);out.put("failedAttemptCount",history.stream().filter(a->a.get("status").equals("FAILED")).count());
        out.put("status",status);for(String[] pair:new String[][]{{"created_at","createdAt"},{"updated_at","updatedAt"},{"expires_at","expiresAt"}})out.put(pair[1],AuthStore.instant(row,pair[0]).toString());
        out.put("paymentId",row.get("payment_id"));if(token)out.put("checkoutPath","/checkout/"+row.get("public_token"));return out;
    }
    @Transactional public Result create(Input raw,String key){
        Input r=validate(raw);text(key,128);if(key.isEmpty()||!key.matches("[A-Za-z0-9._:-]+"))throw new IllegalArgumentException();
        var scope=portal.scope();String merchant=scope.merchantId(),fingerprint=fingerprint(r);Instant now=now();
        var prior=store.jdbc.queryForList("SELECT * FROM "+store.table("payment_links")+" WHERE merchant_id=? AND idempotency_key=?",merchant,key);
        if(!prior.isEmpty()){if(!prior.getFirst().get("request_fingerprint").equals(fingerprint))throw new Conflict();return new Result(render(prior.getFirst(),now,true),true);}
        UUID id=UUID.randomUUID();store.jdbc.update("INSERT INTO "+store.table("payment_links")+" (link_id,merchant_id,public_token,amount,currency,payment_method,gateway_name,customer_reference,description,expires_at,created_at,updated_at,idempotency_key,request_fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",id,merchant,store.opaque(),new BigDecimal(r.amount()),r.currency(),r.paymentMethod(),gateways.route(r.currency()).getGatewayName(),r.customerReference(),r.description(),java.sql.Timestamp.from(now.plusSeconds(r.expiryHours()*3600L)),java.sql.Timestamp.from(now),java.sql.Timestamp.from(now),key,fingerprint);
        audit.success(scope.user(),"PAYMENT_LINK_CREATED",merchant,"PAYMENT_LINK",id.toString(),Map.of());return new Result(render(owned(id,merchant),now,true),false);
    }
    private Map<String,Object> owned(UUID id,String merchant){var rows=store.jdbc.queryForList("SELECT * FROM "+store.table("payment_links")+" WHERE link_id=? AND merchant_id=? FOR UPDATE",id,merchant);if(rows.isEmpty())throw new Missing();return rows.getFirst();}
    @Transactional public Map<String,Object> get(UUID id){var s=portal.scope();return render(owned(id,s.merchantId()),now(),true);}
    @Transactional public Map<String,Object> cancel(UUID id){
        var s=portal.scope();Instant now=now();var row=owned(id,s.merchantId());if(!render(row,now,false).get("status").equals("ACTIVE"))throw new Conflict();
        store.jdbc.update("UPDATE "+store.table("payment_links")+" SET status='CANCELLED',updated_at=? WHERE link_id=?",java.sql.Timestamp.from(now),id);
        audit.success(s.user(),"PAYMENT_LINK_CANCELLED",s.merchantId(),"PAYMENT_LINK",id.toString(),Map.of());return render(owned(id,s.merchantId()),now,true);
    }
    @Transactional public Map<String,Object> list(Map<String,String> p){
        if(!Set.of("page","size","search","status","currency").containsAll(p.keySet()))throw new IllegalArgumentException();
        int page=Integer.parseInt(p.getOrDefault("page","0")),size=Integer.parseInt(p.getOrDefault("size","5"));if(page<0||page>10000||size<1||size>50)throw new IllegalArgumentException();
        String search=text(p.getOrDefault("search",""),100),status=p.getOrDefault("status",""),currency=p.getOrDefault("currency","");
        if(!Set.of("","ACTIVE","CANCELLED","EXPIRED","PAID","PROCESSING").contains(status)||!Set.of("","INR","USD").contains(currency))throw new IllegalArgumentException();
        var s=portal.scope();Instant now=now();String effective="CASE WHEN status='ACTIVE' AND EXISTS(SELECT 1 FROM "+store.table("checkout_attempts")+" a WHERE a.link_id=l.link_id AND a.status IN ('PROCESSING','UNCERTAIN')) THEN 'PROCESSING' WHEN status='ACTIVE' AND expires_at<=? THEN 'EXPIRED' ELSE status END";
        String where=" WHERE merchant_id=? AND ("+effective+"=? OR ?='') AND (currency=? OR ?='') AND (strpos(lower(customer_reference),lower(?))>0 OR link_id::text=?)";
        Object[] args={s.merchantId(),java.sql.Timestamp.from(now),status,status,currency,currency,search,search};
        long total=store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("payment_links")+" l"+where,Long.class,args);
        var all=new ArrayList<Object>(Arrays.asList(args));all.add(size);all.add(page*size);
        var items=store.jdbc.queryForList("SELECT * FROM "+store.table("payment_links")+" l"+where+" ORDER BY created_at DESC,link_id DESC LIMIT ? OFFSET ?",all.toArray()).stream().map(r->render(r,now,false)).toList();
        return Map.of("items",items,"page",page,"size",size,"total",total);
    }
}
