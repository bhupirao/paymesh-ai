package com.paymesh.backend.security.accounts;

import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Server-derived single active ownership context. No merchant selector/financial writes. */
@Service
public class MerchantPortal {
    private final AccountAdministrationLock lock;private final AccountCredentials credentials;private final AccountAuthorization authorization;
    private final UserRoleRepository roles;private final AppUserRepository users;private final AuthStore store;
    private final DashboardAnalytics analytics;private final AccountPasswords passwords;private final AccountAudit audit;private final AdminQueries reads;
    public MerchantPortal(AccountAdministrationLock lock,AccountCredentials credentials,AccountAuthorization authorization,UserRoleRepository roles,AppUserRepository users,AuthStore store,AccountPasswords passwords,AccountAudit audit,AdminQueries reads,DashboardAnalytics analytics){this.analytics=analytics;this.lock=lock;this.credentials=credentials;this.authorization=authorization;this.roles=roles;this.users=users;this.store=store;this.passwords=passwords;this.audit=audit;this.reads=reads;}
    record Scope(AppUser user,String merchantId){}
    Scope scope(){
        lock.acquire();AppUser user=authorization.current(credentials.currentJwtAccount());
        if(!user.getAccountStatus().equals("ACTIVE")||!roles.roles(user.getUserId()).equals(List.of("MERCHANT")))throw new AccountAccessDeniedException();
        var memberships=store.jdbc.queryForList("SELECT merchant_id,active FROM "+store.table("merchant_memberships")+" WHERE user_id=?",user.getUserId());
        if(memberships.size()!=1||!Boolean.TRUE.equals(memberships.getFirst().get("active")))throw new AccountAccessDeniedException();
        String id=(String)memberships.getFirst().get("merchant_id");
        if(store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("merchants")+" m JOIN "+store.table("merchant_administration")+" a USING(merchant_id) WHERE m.merchant_id=? AND m.active AND m.verified AND a.status='ACTIVE'",Integer.class,id)!=1)throw new AccountAccessDeniedException();
        return new Scope(user,id);
    }
    private AdminQueries.Query scoped(AdminQueries.Query q,String id){if(!q.merchantId().isEmpty())throw new IllegalArgumentException();return new AdminQueries.Query(q.page(),q.size(),q.search(),q.status(),q.currency(),id,q.sort(),q.from(),q.to());}
    @Transactional(readOnly=true) public Map<String,Object> analytics(Map<String,String> p){var s=scope();return analytics.read(p,s.merchantId(),false);}
    @Transactional(readOnly=true) public Map<String,Object> dashboard(AdminQueries.Query q){var s=scope();var data=reads.merchantDashboard(scoped(q,s.merchantId()));data.put("profile",profile(s));return data;}
    @Transactional(readOnly=true) public Map<String,Object> financial(String kind,AdminQueries.Query q){var s=scope();return reads.readFinancial(kind,scoped(q,s.merchantId()));}
    @Transactional(readOnly=true) public Map<String,Object> profile(){return profile(scope());}
    private Map<String,Object> profile(Scope s){
        var row=store.jdbc.queryForMap("SELECT m.merchant_id AS \"merchantId\",m.verified AS \"merchantVerified\",m.active AS \"merchantActive\",m.created_at AS \"merchantCreatedAt\",a.status AS \"businessStatus\",a.approved_at AS \"approvedAt\",mm.active AS \"membershipActive\",r.business_name AS \"businessName\",r.email,r.first_name AS \"firstName\",r.last_name AS \"lastName\",r.mobile,r.business_type AS \"businessType\",r.country,r.terms_accepted_at AS \"registeredAt\" FROM "+store.table("merchants")+" m JOIN "+store.table("merchant_administration")+" a USING(merchant_id) JOIN "+store.table("merchant_memberships")+" mm USING(merchant_id) LEFT JOIN "+store.table("merchant_registrations")+" r ON r.merchant_id=m.merchant_id AND r.user_id=mm.user_id WHERE mm.user_id=? AND m.merchant_id=?",s.user().getUserId(),s.merchantId());
        row.replaceAll((k,v)->v instanceof java.sql.Timestamp t?t.toInstant().toString():v);
        row.put("accountStatus",s.user().getAccountStatus());row.put("login",s.user().getLoginNormalized());row.put("registrationAvailable",row.get("registeredAt")!=null);return row;
    }
    @Transactional public void changePassword(char[] current,char[] next,char[] confirm){
        var s=scope();if(!Arrays.equals(next,confirm))throw new IllegalArgumentException();AccountPasswords.validate(next);
        if(!passwords.matches(current,s.user().passwordHash()))throw new AccountAccessDeniedException();
        s.user().replacePasswordForOfflineRecovery(passwords.hash(next));users.saveAndFlush(s.user());
        audit.success(s.user(),"MERCHANT_PASSWORD_CHANGED",s.merchantId(),"ACCOUNT",s.user().getUserId().toString(),Map.of());
    }
}
