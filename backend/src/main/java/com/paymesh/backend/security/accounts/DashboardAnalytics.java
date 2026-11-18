package com.paymesh.backend.security.accounts;

import java.time.*;
import java.sql.Timestamp;
import java.util.*;
import org.springframework.stereotype.Service;

/** Bounded UTC-day read model; caller must authorize and pin ownership before calling. */
@Service
public class DashboardAnalytics {
    private final AuthStore db;private final AuthenticationClock clock;
    public DashboardAnalytics(AuthStore db,AuthenticationClock clock){this.db=db;this.clock=clock;}
    public record Range(Instant from,Instant to,String currency,String merchantId){ }
    public Range range(Map<String,String> p,boolean admin){
        if(!(admin?Set.of("from","to","currency","merchantId"):Set.of("from","to","currency")).containsAll(p.keySet()))throw new IllegalArgumentException();
        LocalDate today=clock.now().atOffset(ZoneOffset.UTC).toLocalDate();
        Instant from=today.minusDays(29).atStartOfDay().toInstant(ZoneOffset.UTC),to=today.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC);
        if(p.containsKey("from")!=p.containsKey("to"))throw new IllegalArgumentException();
        try{if(p.containsKey("from")){from=Instant.parse(p.get("from"));to=Instant.parse(p.get("to"));}}catch(DateTimeException ex){throw new IllegalArgumentException();}
        if(!from.equals(from.atOffset(ZoneOffset.UTC).toLocalDate().atStartOfDay().toInstant(ZoneOffset.UTC))||!to.equals(to.atOffset(ZoneOffset.UTC).toLocalDate().atStartOfDay().toInstant(ZoneOffset.UTC))
            ||!to.isAfter(from)||Duration.between(from,to).compareTo(Duration.ofDays(93))>0||to.isAfter(today.plusDays(1).atStartOfDay().toInstant(ZoneOffset.UTC)))throw new IllegalArgumentException();
        String currency=p.getOrDefault("currency",""),merchant=p.getOrDefault("merchantId","");
        if(!currency.isEmpty()&&!Set.of("INR","USD").contains(currency)||merchant.length()>100||merchant.chars().anyMatch(c->c<32||c==127))throw new IllegalArgumentException();
        return new Range(from,to,currency,merchant);
    }
    private List<Map<String,Object>> rows(String sql,List<Object> args){var rows=db.jdbc.queryForList(sql,args.toArray());rows.forEach(r->r.replaceAll((k,v)->v instanceof java.math.BigDecimal n?n.toPlainString():v));return rows;}
    public Map<String,Object> read(Map<String,String> p,String merchantId,boolean admin){
        Range r=range(p,admin);String scope=admin?r.merchantId():merchantId;
        if(!admin&&(scope==null||scope.isEmpty()))throw new AccountAccessDeniedException();
        String where=" WHERE p.created_at>=? AND p.created_at<?",rw=" WHERE f.created_at>=? AND f.created_at<?";
        List<Object> args=new ArrayList<>(List.of(Timestamp.from(r.from()),Timestamp.from(r.to())));
        if(!scope.isEmpty()){where+=" AND p.merchant_id=?";rw+=" AND p.merchant_id=?";args.add(scope);}
        if(!r.currency().isEmpty()){where+=" AND p.currency=?";rw+=" AND p.currency=?";args.add(r.currency());}
        String pay=" FROM "+db.table("payments")+" p",ref=pay+" JOIN "+db.table("refunds")+" f ON f.payment_id=p.payment_id";
        Map<String,Object> out=new LinkedHashMap<>();out.put("range",Map.of("from",r.from().toString(),"to",r.to().toString(),"timezone","UTC","endExclusive",true));
        out.put("paymentCounts",rows("SELECT p.currency,p.status,count(*) AS count"+pay+where+" GROUP BY p.currency,p.status ORDER BY p.currency,p.status",args));
        out.put("refundCounts",rows("SELECT p.currency,f.status,count(*) AS count"+ref+rw+" GROUP BY p.currency,f.status ORDER BY p.currency,f.status",args));
        out.put("paymentMethods",rows("SELECT p.currency,p.payment_method AS \"paymentMethod\",count(*) AS count"+pay+where+" GROUP BY p.currency,p.payment_method ORDER BY p.currency,p.payment_method",args));
        var totals=rows("SELECT currency,sum(payment_amount) AS \"paymentAmount\",sum(refund_amount) AS \"refundAmount\" FROM (SELECT p.currency,sum(p.amount) AS payment_amount,0::numeric AS refund_amount"+pay+where+" GROUP BY p.currency UNION ALL SELECT p.currency,0::numeric,sum(f.amount)"+ref+rw+" GROUP BY p.currency) x GROUP BY currency ORDER BY currency",new ArrayList<>(){{addAll(args);addAll(args);}});
        out.put("amountComparison",totals);
        List<Object> daily=new ArrayList<>(List.of(r.from().atOffset(ZoneOffset.UTC).toLocalDate().toString(),r.to().atOffset(ZoneOffset.UTC).toLocalDate().toString()));daily.addAll(args);
        String currencies=r.currency().isEmpty()?"('INR'),('USD')":"('"+r.currency()+"')"; // currency was allowlisted above.
        out.put("dailyPayments",rows("WITH days AS (SELECT generate_series(?::date::timestamp,?::date::timestamp-interval '1 day',interval '1 day')::date AS day),currencies(currency) AS (VALUES "+currencies+"),stats AS (SELECT (p.created_at AT TIME ZONE 'UTC')::date AS day,p.currency,count(*) AS count,sum(p.amount) AS amount"+pay+where+" GROUP BY 1,p.currency) SELECT to_char(d.day,'YYYY-MM-DD') AS date,c.currency,COALESCE(s.count,0) AS count,COALESCE(s.amount,0.00) AS amount FROM days d CROSS JOIN currencies c LEFT JOIN stats s ON s.day=d.day AND s.currency=c.currency ORDER BY d.day,c.currency",daily));
        if(admin)out.put("merchantCounts",rows("SELECT status,count(*) AS count FROM "+db.table("merchant_administration")+" GROUP BY status ORDER BY status",List.of()));
        return out;
    }
}
