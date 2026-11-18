package com.paymesh.backend.security.accounts;

import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Reuses the same serialization lock, real JWT identity and success audit transaction. */
@Service
public class MerchantAdministration {
    private final AccountCredentials credentials;
    private final AccountAuthorization authorization;
    private final AccountAdministrationLock lock;
    private final AccountAudit audit;
    private final AuthStore store;
    private final AppUserRepository users;
    private final MerchantRepository merchants;
    private final MerchantMembershipRepository memberships;
    private final UserRoleRepository roles;
    private final AccountPasswords passwords;
    public MerchantAdministration(AccountCredentials credentials,AccountAuthorization authorization,AccountAdministrationLock lock,
        AccountAudit audit,AuthStore store,AppUserRepository users,MerchantRepository merchants,
        MerchantMembershipRepository memberships,UserRoleRepository roles,AccountPasswords passwords) {
        this.credentials=credentials;this.authorization=authorization;this.lock=lock;this.audit=audit;this.store=store;
        this.users=users;this.merchants=merchants;this.memberships=memberships;this.roles=roles;this.passwords=passwords;
    }
    public static class Conflict extends RuntimeException {}
    public static class Missing extends RuntimeException {}
    AppUser actor(){lock.acquire();return authorization.requireAdmin(credentials.currentJwtAccount());}
    static String bounded(String value,int max){
        if(value==null||value.isBlank()||value.length()>max||value.chars().anyMatch(c->c<32||c==127))throw new IllegalArgumentException();
        return value.strip();
    }
    @Transactional
    public Map<String,Object> transition(String merchantId,String action,String reason,String reference,boolean attested) {
        AppUser actor=actor();
        if(merchantId==null||merchantId.isEmpty()||merchantId.length()>100)throw new IllegalArgumentException();
        var state=store.jdbc.queryForList("SELECT * FROM "+store.table("merchant_administration")+" WHERE merchant_id=? FOR UPDATE",merchantId);
        if(state.isEmpty())throw new Missing();
        var membership=store.jdbc.queryForList("SELECT user_id FROM "+store.table("merchant_memberships")+" WHERE merchant_id=?",merchantId);
        // Never globally change a shared/mixed-role identity by guessing ownership.
        if(membership.size()!=1)throw new Conflict();
        UUID targetId=(UUID)membership.getFirst().get("user_id");
        if(!roles.roles(targetId).equals(List.of("MERCHANT"))||store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("merchant_memberships")+" WHERE user_id=?",Integer.class,targetId)!=1)throw new Conflict();
        AppUser target=users.findById(targetId).orElseThrow(Missing::new);
        Merchant merchant=merchants.findById(merchantId).orElseThrow(Missing::new);
        MerchantMembership member=memberships.findById(new MerchantMembership.Id(targetId,merchantId)).orElseThrow(Conflict::new);
        if(!target.isEnabled())throw new Conflict();
        String from=(String)state.getFirst().get("status"),to;
        Map<String,Object> metadata=new HashMap<>();metadata.put("from",from);
        switch(action) {
            case "approve" -> {
                if(!from.equals("PENDING_APPROVAL")||!target.getAccountStatus().equals("PENDING_APPROVAL")||merchant.isVerified()||member.isActive())throw new Conflict();
                if(store.jdbc.queryForObject("SELECT count(*) FROM "+store.table("merchant_registrations")+" WHERE user_id=? AND merchant_id=?",Integer.class,targetId,merchantId)!=1)throw new Conflict();
                if(!attested||reference==null||!reference.matches("[A-Za-z0-9][A-Za-z0-9._/\\-]{2,99}"))throw new IllegalArgumentException();
                merchant.verify(actor.getUserId());member.activate(actor.getUserId());to="ACTIVE";
                metadata.put("reviewReference",reference);metadata.put("ownershipAttested",true);
            }
            case "reject" -> {
                if(!from.equals("PENDING_APPROVAL")||!target.getAccountStatus().equals("PENDING_APPROVAL")||merchant.isVerified()||member.isActive())throw new Conflict();
                reason=bounded(reason,500);to="REJECTED";member.revoke();merchant.administrationActive(false);
            }
            case "suspend" -> {
                if(!from.equals("ACTIVE")||!target.getAccountStatus().equals("ACTIVE")||!merchant.isActive()||!merchant.isVerified()||!member.isActive())throw new Conflict();
                reason=bounded(reason,500);to="SUSPENDED";member.revoke();merchant.administrationActive(false);
            }
            case "reactivate" -> {
                if(!from.equals("SUSPENDED")||!target.getAccountStatus().equals("SUSPENDED")||!merchant.isVerified()||state.getFirst().get("approved_at")==null||member.isActive())throw new Conflict();
                reason=bounded(reason,500);to="ACTIVE";merchant.administrationActive(true);member.activate(actor.getUserId());
            }
            default -> throw new IllegalArgumentException();
        }
        target.administrationStatus(to);users.saveAndFlush(target);merchants.saveAndFlush(merchant);memberships.saveAndFlush(member);
        store.jdbc.update("UPDATE "+store.table("merchant_administration")+" SET status=?,approved_at=COALESCE(approved_at,?),approved_by=COALESCE(approved_by,?),last_action_at=CURRENT_TIMESTAMP,last_action_by=?,reason=?,review_reference=COALESCE(?,review_reference) WHERE merchant_id=?",
            to,merchant.getVerifiedAt()==null?null:java.sql.Timestamp.from(merchant.getVerifiedAt()),merchant.getVerifiedBy(),actor.getUserId(),reason,reference,merchantId);
        metadata.put("to",to);if(reason!=null)metadata.put("reason",reason);
        audit.success(actor,"MERCHANT_"+action.toUpperCase(Locale.ROOT),merchantId,"MERCHANT",merchantId,metadata);
        return Map.of("merchantId",merchantId,"status",to,"message","Administrative action committed. Refresh authoritative details.");
    }
    @Transactional
    public void changePassword(char[] current,char[] password,char[] confirmation) {
        AppUser actor=actor();
        if(!Arrays.equals(password,confirmation))throw new IllegalArgumentException();
        AccountPasswords.validate(password);
        if(!passwords.matches(current,actor.passwordHash()))throw new AccountAccessDeniedException();
        actor.replacePasswordForOfflineRecovery(passwords.hash(password));users.saveAndFlush(actor);
        audit.success(actor,"ADMIN_PASSWORD_CHANGED",null,"ACCOUNT",actor.getUserId().toString(),Map.of());
    }
}
