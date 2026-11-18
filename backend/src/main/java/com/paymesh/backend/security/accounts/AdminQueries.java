package com.paymesh.backend.security.accounts;

import java.sql.Timestamp;
import java.time.*;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Parameterized read models, explicit projections and exact decimal text; no financial mutation. */
@Service
@Transactional(readOnly=true)
public class AdminQueries {
    private final DashboardAnalytics analytics;private final AuthStore db;
    private final MerchantAdministration administration;
    public AdminQueries(AuthStore db,MerchantAdministration administration,DashboardAnalytics analytics){this.db=db;this.administration=administration;this.analytics=analytics;}
    public record Query(int page,int size,String search,String status,String currency,String merchantId,String sort,Instant from,Instant to) {
        public static Query parse(Map<String,String> p) {
            if(!Set.of("page","size","search","status","currency","merchantId","sort","from","to").containsAll(p.keySet()))throw new IllegalArgumentException();
            int page=Integer.parseInt(p.getOrDefault("page","0")),size=Integer.parseInt(p.getOrDefault("size","25"));
            if(page<0||page>10000||size<1||size>100)throw new IllegalArgumentException();
            String search=p.getOrDefault("search",""),status=p.getOrDefault("status",""),currency=p.getOrDefault("currency",""),merchant=p.getOrDefault("merchantId",""),sort=p.getOrDefault("sort","newest");
            if(search.length()>100||merchant.length()>100||search.chars().anyMatch(c->c<32)||merchant.chars().anyMatch(c->c<32)||!Set.of("newest","oldest").contains(sort))throw new IllegalArgumentException();
            if(!status.isEmpty()&&!Set.of("PENDING_APPROVAL","ACTIVE","REJECTED","SUSPENDED","CREATED","PROCESSING","SUCCESS","FAILED","CANCELLED","REFUNDED","PENDING").contains(status))throw new IllegalArgumentException();
            if(!currency.isEmpty()&&!Set.of("INR","USD").contains(currency))throw new IllegalArgumentException();
            Instant from,to;try{from=p.containsKey("from")?Instant.parse(p.get("from")):null;to=p.containsKey("to")?Instant.parse(p.get("to")):null;}catch(java.time.DateTimeException ex){throw new IllegalArgumentException();}
            if(from!=null&&to!=null&&(to.isBefore(from)||Duration.between(from,to).compareTo(Duration.ofDays(366))>0))throw new IllegalArgumentException();
            return new Query(page,size,search,status,currency,merchant,sort,from,to);
        }
    }
    private String t(String name){return db.table(name);}
    private List<Map<String,Object>> rows(String sql,Object... args){
        var result=db.jdbc.queryForList(sql,args);
        result.forEach(row->row.replaceAll((k,v)->v instanceof Timestamp time?time.toInstant().toString():v instanceof java.math.BigDecimal amount?amount.toPlainString():v));return result;
    }
    private Map<String,Object> paged(String projection,String source,String where,List<Object> args,String order,Query q) {
        long count=db.jdbc.queryForObject("SELECT count(*) "+source+where,Long.class,args.toArray());
        List<Object> values=new ArrayList<>(args);values.add(q.size());values.add(q.page()*q.size());
        return Map.of("items",rows("SELECT "+projection+" "+source+where+" ORDER BY "+order.replace(", ",(q.sort().equals("oldest")?" ASC, ":" DESC, "))+(q.sort().equals("oldest")?" ASC":" DESC")+" LIMIT ? OFFSET ?",values.toArray()),"page",q.page(),"size",q.size(),"total",count);
    }
    private String dates(Query q,String column,List<Object> args){String sql="";if(q.from()!=null){sql+=" AND "+column+">=?";args.add(Timestamp.from(q.from()));}if(q.to()!=null){sql+=" AND "+column+"<=?";args.add(Timestamp.from(q.to()));}return sql;}
    private String financialWhere(Query q,String statusColumn,List<Object> args){
        String sql=" WHERE 1=1";
        if(!q.status().isEmpty()){sql+=" AND "+statusColumn+"=?";args.add(q.status());}
        if(!q.currency().isEmpty()){sql+=" AND p.currency=?";args.add(q.currency());}
        if(!q.merchantId().isEmpty()){sql+=" AND p.merchant_id=?";args.add(q.merchantId());}
        if(!q.search().isEmpty()){sql+=" AND (p.payment_id::text=? OR p.customer_id=?)";args.add(q.search());args.add(q.search());}
        return sql;
    }
    private String merchantSource(){return " FROM "+t("merchants")+" m JOIN "+t("merchant_administration")+" a ON a.merchant_id=m.merchant_id LEFT JOIN "+t("merchant_registrations")+" r ON r.merchant_id=m.merchant_id";}
    private String merchantProjection(){return "m.merchant_id AS \"merchantId\",a.status,m.verified,m.active,a.approved_at AS \"approvedAt\",a.approved_by AS \"approvedBy\",a.last_action_at AS \"lastActionAt\",a.reason,a.review_reference AS \"reviewReference\",m.created_at AS \"createdAt\",r.user_id AS \"registrationUserId\",r.business_name AS \"businessName\",r.email,r.first_name AS \"firstName\",r.last_name AS \"lastName\",r.mobile,r.business_type AS \"businessType\",r.country";}
    public Map<String,Object> merchants(Query q){
        administration.actor();List<Object> args=new ArrayList<>();String where=" WHERE 1=1";
        if(!q.status().isEmpty()){if(!Set.of("PENDING_APPROVAL","ACTIVE","REJECTED","SUSPENDED").contains(q.status()))throw new IllegalArgumentException();where+=" AND a.status=?";args.add(q.status());}
        if(!q.search().isEmpty()){String literal="%"+q.search().replace("!","!!").replace("%","!%").replace("_","!_")+"%";where+=" AND (m.merchant_id ILIKE ? ESCAPE '!' OR r.business_name ILIKE ? ESCAPE '!' OR r.email ILIKE ? ESCAPE '!')";args.add(literal);args.add(literal);args.add(literal);}
        if(!q.merchantId().isEmpty()){where+=" AND m.merchant_id=?";args.add(q.merchantId());}
        where+=dates(q,"m.created_at",args);
        return paged(merchantProjection(),merchantSource(),where,args,"m.created_at, m.merchant_id",q);
    }
    public Map<String,Object> merchant(String id){administration.actor();if(id==null||id.isEmpty()||id.length()>100)throw new IllegalArgumentException();var result=rows("SELECT "+merchantProjection()+merchantSource()+" WHERE m.merchant_id=?",id);if(result.isEmpty())throw new MerchantAdministration.Missing();return result.getFirst();}
    private String paymentProjection(){return "p.payment_id AS \"paymentId\",p.merchant_id AS \"merchantId\",p.amount AS amount,p.currency,p.customer_id AS \"customerId\",p.payment_method AS \"paymentMethod\",p.status,p.created_at AS \"createdAt\"";}
    private String refundProjection(){return "f.refund_id AS \"refundId\",f.payment_id AS \"paymentId\",p.merchant_id AS \"merchantId\",f.amount AS amount,p.currency,f.status,f.created_at AS \"createdAt\"";}
    public Map<String,Object> financial(String kind,Query q){administration.actor();return readFinancial(kind,q);}
    Map<String,Object> readFinancial(String kind,Query q){boolean refund=kind.equals("refunds");List<Object> args=new ArrayList<>();String where=financialWhere(q,refund?"f.status":"p.status",args)+dates(q,refund?"f.created_at":"p.created_at",args);return paged(refund?refundProjection():paymentProjection()," FROM "+t("payments")+" p"+(refund?" JOIN "+t("refunds")+" f ON f.payment_id=p.payment_id":""),where,args,refund?"f.created_at, f.refund_id":"p.created_at, p.payment_id",q);}
    public Map<String,Object> financialDetail(String kind,UUID id){administration.actor();boolean refund=kind.equals("refunds");var result=rows("SELECT "+(refund?refundProjection():paymentProjection())+" FROM "+t("payments")+" p"+(refund?" JOIN "+t("refunds")+" f ON f.payment_id=p.payment_id":"")+" WHERE "+(refund?"f.refund_id":"p.payment_id")+"=?",id);if(result.isEmpty())throw new MerchantAdministration.Missing();return result.getFirst();}
    public Map<String,Object> analytics(Map<String,String> p){administration.actor();return analytics.read(p,"",true);}
    public Map<String,Object> dashboard(Query q){
        administration.actor();List<Object> pa=new ArrayList<>(),ra=new ArrayList<>();
        String pw=financialWhere(q,"p.status",pa)+dates(q,"p.created_at",pa),rw=financialWhere(q,"f.status",ra)+dates(q,"f.created_at",ra);
        String payments=" FROM "+t("payments")+" p",refunds=payments+" JOIN "+t("refunds")+" f ON f.payment_id=p.payment_id";
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("totalMerchants",db.jdbc.queryForObject("SELECT count(*) FROM "+t("merchants"),Long.class));
        result.put("merchantCounts",rows("SELECT status,count(*) AS count FROM "+t("merchant_administration")+" GROUP BY status ORDER BY status"));
        result.put("pendingRegistrations",db.jdbc.queryForObject("SELECT count(*) FROM "+t("merchant_registrations")+" r JOIN "+t("merchant_administration")+" a ON a.merchant_id=r.merchant_id WHERE a.status='PENDING_APPROVAL'",Long.class));
        result.put("paymentCounts",rows("SELECT p.status,count(*) AS count"+payments+pw+" GROUP BY p.status ORDER BY p.status",pa.toArray()));
        result.put("refundCounts",rows("SELECT f.status,count(*) AS count"+refunds+rw+" GROUP BY f.status ORDER BY f.status",ra.toArray()));
        result.put("paymentAmounts",rows("SELECT p.currency,p.status,sum(p.amount) AS amount"+payments+pw+" GROUP BY p.currency,p.status ORDER BY p.currency,p.status",pa.toArray()));
        result.put("refundAmounts",rows("SELECT p.currency,f.status,sum(f.amount) AS amount"+refunds+rw+" GROUP BY p.currency,f.status ORDER BY p.currency,f.status",ra.toArray()));
        result.put("recentRegistrations",rows("SELECT r.merchant_id AS \"merchantId\",r.business_name AS \"businessName\",a.status,r.terms_accepted_at AS \"createdAt\" FROM "+t("merchant_registrations")+" r JOIN "+t("merchant_administration")+" a ON a.merchant_id=r.merchant_id ORDER BY r.terms_accepted_at DESC,r.user_id LIMIT 5"));
        result.put("recentPayments",rows("SELECT "+paymentProjection()+payments+pw+" ORDER BY p.created_at DESC,p.payment_id LIMIT 5",pa.toArray()));
        return result;
    }
    Map<String,Object> merchantDashboard(Query q){
        List<Object> pa=new ArrayList<>(),ra=new ArrayList<>();
        String pw=financialWhere(q,"p.status",pa)+dates(q,"p.created_at",pa),rw=financialWhere(q,"f.status",ra)+dates(q,"f.created_at",ra);
        String payments=" FROM "+t("payments")+" p",refunds=payments+" JOIN "+t("refunds")+" f ON f.payment_id=p.payment_id";
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("totalPayments",db.jdbc.queryForObject("SELECT count(*)"+payments+pw,Long.class,pa.toArray()));
        result.put("paymentCounts",rows("SELECT p.status,count(*) AS count"+payments+pw+" GROUP BY p.status ORDER BY p.status",pa.toArray()));
        result.put("refundCounts",rows("SELECT f.status,count(*) AS count"+refunds+rw+" GROUP BY f.status ORDER BY f.status",ra.toArray()));
        result.put("paymentAmounts",rows("SELECT p.currency,p.status,sum(p.amount) AS amount"+payments+pw+" GROUP BY p.currency,p.status ORDER BY p.currency,p.status",pa.toArray()));
        result.put("refundAmounts",rows("SELECT p.currency,f.status,sum(f.amount) AS amount"+refunds+rw+" GROUP BY p.currency,f.status ORDER BY p.currency,f.status",ra.toArray()));
        result.put("recentPayments",rows("SELECT "+paymentProjection()+payments+pw+" ORDER BY p.created_at DESC,p.payment_id DESC LIMIT 5",pa.toArray()));
        result.put("recentRefunds",rows("SELECT "+refundProjection()+refunds+rw+" ORDER BY f.created_at DESC,f.refund_id DESC LIMIT 5",ra.toArray()));
        return result;
    }
    public Map<String,Object> audit(Query q){administration.actor();List<Object> args=new ArrayList<>();String where=" WHERE 1=1";if(!q.search().isEmpty()){where+=" AND e.event_type=?";args.add(q.search());}if(!q.merchantId().isEmpty()){where+=" AND e.target_merchant_id=?";args.add(q.merchantId());}where+=dates(q,"e.occurred_at",args);return paged("e.event_id AS \"eventId\",e.actor_user_id AS \"actorUserId\",e.event_type AS \"eventType\",e.target_merchant_id AS \"merchantId\",e.resource_type AS \"resourceType\",e.resource_id AS \"resourceId\",e.outcome,e.occurred_at AS \"occurredAt\""," FROM "+t("security_audit_events")+" e",where,args,"e.occurred_at, e.event_id",q);}
    public Map<String,Object> accounts(Query q){administration.actor();List<Object> args=new ArrayList<>();String where=" WHERE EXISTS(SELECT 1 FROM "+t("user_roles")+" r WHERE r.user_id=u.user_id AND r.role_name='ADMIN')";if(!q.search().isEmpty()){where+=" AND u.login_normalized=?";args.add(q.search().strip().toLowerCase(Locale.ROOT));}return paged("u.user_id AS \"userId\",u.login_normalized AS login,u.enabled,u.account_status AS \"accountStatus\",u.created_at AS \"createdAt\""," FROM "+t("app_users")+" u",where,args,"u.created_at, u.user_id",q);}
    public Map<String,Object> profile(){AppUser actor=administration.actor();return Map.of("userId",actor.getUserId(),"login",actor.getLoginNormalized(),"enabled",actor.isEnabled(),"accountStatus",actor.getAccountStatus(),"roles",db.jdbc.queryForList("SELECT role_name FROM "+t("user_roles")+" WHERE user_id=? ORDER BY role_name",String.class,actor.getUserId()));}
}
