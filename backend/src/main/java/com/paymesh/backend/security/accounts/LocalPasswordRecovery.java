package com.paymesh.backend.security.accounts;

import java.time.*;
import java.sql.Timestamp;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Deliberately insecure on-screen OTP, gated by verified local deployment AND operator eligibility. */
@Service
public class LocalPasswordRecovery {
    private final AuthStore store;private final AuthenticationClock clock;private final LocalDemoRecoveryGate gate;
    private final AccountAdministrationLock lock;private final AppUserRepository users;private final UserRoleRepository roles;private final AccountPasswords passwords;private final AccountAudit audit;
    private final Map<String,Deque<Instant>> requesters=new HashMap<>();
    public LocalPasswordRecovery(AuthStore store,AuthenticationClock clock,LocalDemoRecoveryGate gate,AccountAdministrationLock lock,AppUserRepository users,UserRoleRepository roles,AccountPasswords passwords,AccountAudit audit){
        this.store=store;this.clock=clock;this.gate=gate;this.lock=lock;this.users=users;this.roles=roles;this.passwords=passwords;this.audit=audit;
    }
    public boolean enabled(){return gate.enabled();}
    private void requireEnabled(){if(!enabled())throw new Disabled();}
    public static class Disabled extends RuntimeException {}
    public static class Limited extends RuntimeException {}
    public static class Invalid extends RuntimeException {}
    private synchronized void budget(String requester) {
        Instant cutoff=clock.now().minusSeconds(600);requesters.entrySet().removeIf(e->e.getValue().peekLast().isBefore(cutoff));
        if(requester==null||requester.length()>64)throw new Limited();var q=requesters.get(requester);
        if(q==null){if(requesters.size()>=1024)throw new Limited();q=new ArrayDeque<>();requesters.put(requester,q);}
        while(!q.isEmpty()&&q.peekFirst().isBefore(cutoff))q.removeFirst();if(q.size()>=20)throw new Limited();q.addLast(clock.now());
    }
    private boolean eligible(AppUser u,String portal) {
        if(u==null||!u.isEnabled()||!Set.of("ACTIVE","PENDING_APPROVAL").contains(u.getAccountStatus()))return false;
        var actual=new HashSet<>(roles.roles(u.getUserId()));if(!actual.equals(Set.of(portal)))return false;
        if(portal.equals("ADMIN")&&!"ACTIVE".equals(u.getAccountStatus()))return false;
        return Boolean.TRUE.equals(store.jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM "+store.table("demo_recovery_eligibility")+" WHERE user_id=? AND portal=? AND enabled)",Boolean.class,u.getUserId(),portal));
    }
    public record Challenge(String challengeId,String otp,Instant expiresAt,int resendAfterSeconds) {@Override public String toString(){return "Challenge [redacted]";}}
    @Transactional public Challenge forgot(String identity,String portal,String requester) {
        requireEnabled();budget(requester);lock.acquire();
        if(!Set.of("ADMIN","MERCHANT").contains(portal))throw new Invalid();
        String normalized;try{normalized=AccountCredentials.normalizeLogin(identity);}catch(IllegalArgumentException ex){normalized="";}
        AppUser user=users.findByLoginNormalized(normalized).orElse(null);Instant now=clock.now();UUID id=UUID.randomUUID();
        if(user==null||!eligible(user,portal))return new Challenge(id.toString(),null,now.plusSeconds(300),60);
        var recent=store.jdbc.queryForList("SELECT created_at FROM "+store.table("password_recovery_challenges")+" WHERE user_id=? AND created_at>? ORDER BY created_at DESC",user.getUserId(),Timestamp.from(now.minusSeconds(600)));
        if(!recent.isEmpty()&&(AuthStore.instant(recent.getFirst(),"created_at").plusSeconds(60).isAfter(now)||recent.size()>=5))throw new Limited();
        invalidate(user.getUserId());cleanup();String otp=store.otp();
        store.jdbc.update("INSERT INTO "+store.table("password_recovery_challenges")+"(challenge_id,user_id,portal,purpose,otp_digest,authorization_version,created_at,expires_at) VALUES (?,?,?,'LOCAL_DEMO_PASSWORD_RESET',?,?,?,?)",id,user.getUserId(),portal,AuthStore.keyed(gate.key(),id+":"+portal+":"+otp),user.getAuthorizationVersion(),Timestamp.from(now),Timestamp.from(now.plusSeconds(300)));
        return new Challenge(id.toString(),otp,now.plusSeconds(300),60);
    }
    private void cleanup(){store.jdbc.update("DELETE FROM "+store.table("password_recovery_challenges")+" WHERE challenge_id IN (SELECT challenge_id FROM "+store.table("password_recovery_challenges")+" WHERE expires_at<? ORDER BY expires_at LIMIT 100)",Timestamp.from(clock.now().minusSeconds(86400)));}
    private void invalidate(UUID user){store.jdbc.update("UPDATE "+store.table("password_recovery_challenges")+" SET consumed_at=COALESCE(consumed_at,?) WHERE user_id=?",Timestamp.from(clock.now()),user);store.jdbc.update("UPDATE "+store.table("password_reset_authorizations")+" SET consumed_at=COALESCE(consumed_at,?) WHERE challenge_id IN (SELECT challenge_id FROM "+store.table("password_recovery_challenges")+" WHERE user_id=?)",Timestamp.from(clock.now()),user);}
    private List<Map<String,Object>> challenge(UUID id){return store.jdbc.queryForList("SELECT * FROM "+store.table("password_recovery_challenges")+" WHERE challenge_id=? FOR UPDATE",id);}
    // Null means invalid: attempt counters and exhaustion must commit even on failure.
    @Transactional public String verify(UUID id,String portal,String otp,String requester) {
        requireEnabled();budget(requester);lock.acquire();var rows=challenge(id);if(rows.isEmpty())return null;var c=rows.getFirst();
        AppUser user=users.findById((UUID)c.get("user_id")).orElse(null);
        if(c.get("consumed_at")!=null||!AuthStore.instant(c,"expires_at").isAfter(clock.now())||((Number)c.get("failed_attempts")).intValue()>=5||!portal.equals(c.get("portal"))||!eligible(user,portal)||((Number)c.get("authorization_version")).longValue()!=user.getAuthorizationVersion())return null;
        if(otp==null||!otp.matches("[0-9]{6}")||!AuthStore.equal((String)c.get("otp_digest"),AuthStore.keyed(gate.key(),id+":"+portal+":"+otp))) {
            store.jdbc.update("UPDATE "+store.table("password_recovery_challenges")+" SET failed_attempts=failed_attempts+1 WHERE challenge_id=?",id);return null;
        }
        store.jdbc.update("UPDATE "+store.table("password_recovery_challenges")+" SET consumed_at=? WHERE challenge_id=?",Timestamp.from(clock.now()),id);
        String token=store.opaque();store.jdbc.update("INSERT INTO "+store.table("password_reset_authorizations")+"(authorization_id,challenge_id,token_digest,expires_at) VALUES (?,?,?,?)",UUID.randomUUID(),id,AuthStore.digest(token),Timestamp.from(clock.now().plusSeconds(300)));return token;
    }
    @Transactional public void reset(UUID challengeId,String portal,String token,char[] password,char[] confirmation,String requester) {
        requireEnabled();budget(requester);InitialAdminProvisioner.requireMatchingPasswords(password,confirmation);AccountPasswords.validate(password);
        if(!AuthStore.opaqueFormat(token))throw new Invalid();lock.acquire();var rows=challenge(challengeId);if(rows.isEmpty())throw new Invalid();var c=rows.getFirst();
        var grants=store.jdbc.queryForList("SELECT * FROM "+store.table("password_reset_authorizations")+" WHERE challenge_id=? AND token_digest=? FOR UPDATE",challengeId,AuthStore.digest(token));
        if(grants.isEmpty())throw new Invalid();var grant=grants.getFirst();AppUser user=users.findById((UUID)c.get("user_id")).orElse(null);
        if(grant.get("consumed_at")!=null||!AuthStore.instant(grant,"expires_at").isAfter(clock.now())||!portal.equals(c.get("portal"))||!eligible(user,portal)||((Number)c.get("authorization_version")).longValue()!=user.getAuthorizationVersion())throw new Invalid();
        user.replacePasswordForOfflineRecovery(passwords.hash(password));users.saveAndFlush(user);invalidate(user.getUserId());
        audit.localDemoPasswordRecovery(user.getUserId()); // Same transaction; V10 account trigger revokes all sessions.
    }
}
