package com.paymesh.backend.security.accounts;

import java.time.*;
import java.sql.Timestamp;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;
import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import com.paymesh.backend.security.accounts.AccountTokenStateService.TokenAccount;

@Service
public class PersistentSessions {
    private final AuthStore store;private final AccountTokenStateService accounts;private final AuthenticationClock clock;
    private final AccountAdministrationLock lock;private final AppUserRepository users;
    private final long rememberedSeconds,shortSeconds,idleSeconds,rememberedIdleSeconds;
    public PersistentSessions(AuthStore store,AccountTokenStateService accounts,AuthenticationClock clock,AccountAdministrationLock lock,AppUserRepository users,
       @Value("${paymesh.sessions.remember-seconds:2592000}") long remembered,@Value("${paymesh.sessions.short-seconds:28800}") long shorter,@Value("${paymesh.sessions.idle-seconds:28800}") long idle,@Value("${paymesh.sessions.remember-idle-seconds:604800}") long rememberedIdle) {
        if(rememberedIdle<900||rememberedIdle>2592000)throw new IllegalStateException("Invalid remembered idle lifetime");
        if(remembered<900||remembered>2592000||shorter<900||shorter>28800||idle<900||idle>28800)throw new IllegalStateException("Invalid session lifetime");
        this.store=store;this.accounts=accounts;this.clock=clock;this.lock=lock;this.users=users;rememberedSeconds=remembered;shortSeconds=shorter;idleSeconds=idle;rememberedIdleSeconds=rememberedIdle;
    }
    public record Grant(UUID sessionId,String refreshToken,boolean rememberMe,Instant expiresAt,TokenAccount account) { @Override public String toString(){return "Session grant [redacted]";} }
    private String roles(TokenAccount a){return a.roles().stream().map(Enum::name).sorted().reduce((a1,b)->a1+","+b).orElse("");}
    @Transactional
    public Grant create(AuthenticatedAccount principal,boolean remember) {
        lock.acquire();cleanup();var account=accounts.forAuthenticated(principal);Instant now=clock.now(),expires=now.plusSeconds(remember?rememberedSeconds:shortSeconds);UUID id=UUID.randomUUID();
        store.jdbc.update("INSERT INTO "+store.table("auth_sessions")+"(session_id,user_id,authorization_version,account_status,roles_snapshot,remember_me,created_at,absolute_expires_at,idle_expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
            id,account.userId(),account.authorizationVersion(),account.accountStatus(),roles(account),remember,Timestamp.from(now),Timestamp.from(expires),Timestamp.from(now.plusSeconds(remember?rememberedIdleSeconds:idleSeconds).isBefore(expires)?now.plusSeconds(remember?rememberedIdleSeconds:idleSeconds):expires));
        return token(id,remember,expires,account);
    }
    private Grant token(UUID id,boolean remember,Instant expires,TokenAccount account) {
        String raw=store.opaque();store.jdbc.update("INSERT INTO "+store.table("auth_refresh_tokens")+"(token_id,session_id,token_digest,created_at) VALUES (?,?,?,?)",UUID.randomUUID(),id,AuthStore.digest(raw),Timestamp.from(clock.now()));
        return new Grant(id,raw,remember,expires,account);
    }
    // Return null (not throw) on replay so the family revocation commits.
    @Transactional
    public Grant refresh(String raw) {
        if(!AuthStore.opaqueFormat(raw))return null;
        lock.acquire();
        var tokens=store.jdbc.queryForList("SELECT * FROM "+store.table("auth_refresh_tokens")+" WHERE token_digest=?",AuthStore.digest(raw));if(tokens.isEmpty())return null;
        var credential=tokens.getFirst();UUID id=(UUID)credential.get("session_id");
        var rows=store.jdbc.queryForList("SELECT * FROM "+store.table("auth_sessions")+" WHERE session_id=? FOR UPDATE",id);if(rows.isEmpty())return null;
        var row=rows.getFirst();
        if(credential.get("used_at")!=null){revoke(id);return null;}
        TokenAccount account;
        try{account=accounts.forToken((UUID)row.get("user_id"));}catch(AccountAccessDeniedException ex){revoke(id);return null;}
        if(!valid(row,account)){revoke(id);return null;}
        Instant now=clock.now(),expires=AuthStore.instant(row,"absolute_expires_at");boolean remember=(boolean)row.get("remember_me");
        store.jdbc.update("UPDATE "+store.table("auth_refresh_tokens")+" SET used_at=? WHERE token_id=?",Timestamp.from(now),credential.get("token_id"));
        store.jdbc.update("UPDATE "+store.table("auth_sessions")+" SET idle_expires_at=? WHERE session_id=?",Timestamp.from(now.plusSeconds(remember?rememberedIdleSeconds:idleSeconds).isBefore(expires)?now.plusSeconds(remember?rememberedIdleSeconds:idleSeconds):expires),id);
        return token(id,(boolean)row.get("remember_me"),expires,account);
    }
    private boolean valid(Map<String,Object> row,TokenAccount a) {
        return row.get("revoked_at")==null&&AuthStore.instant(row,"absolute_expires_at").isAfter(clock.now())&&AuthStore.instant(row,"idle_expires_at").isAfter(clock.now())
            && ((Number)row.get("authorization_version")).longValue()==a.authorizationVersion()&&Objects.equals(row.get("account_status"),a.accountStatus())&&Objects.equals(row.get("roles_snapshot"),roles(a));
    }
    @Transactional(readOnly=true)
    public boolean validAccess(UUID id,TokenAccount account) {
        var rows=store.jdbc.queryForList("SELECT * FROM "+store.table("auth_sessions")+" WHERE session_id=? AND user_id=?",id,account.userId());return !rows.isEmpty()&&valid(rows.getFirst(),account);
    }
    private void cleanup(){store.jdbc.update("DELETE FROM "+store.table("auth_sessions")+" WHERE session_id IN (SELECT session_id FROM "+store.table("auth_sessions")+" WHERE absolute_expires_at<? ORDER BY absolute_expires_at LIMIT 100)",Timestamp.from(clock.now().minusSeconds(86400)));}
    private void revoke(UUID id){store.jdbc.update("UPDATE "+store.table("auth_sessions")+" SET revoked_at=COALESCE(revoked_at,?) WHERE session_id=?",Timestamp.from(clock.now()),id);}
    @Transactional public void logout(String raw) {
        if(!AuthStore.opaqueFormat(raw))return;lock.acquire();
        var rows=store.jdbc.queryForList("SELECT session_id FROM "+store.table("auth_refresh_tokens")+" WHERE token_digest=?",AuthStore.digest(raw));if(!rows.isEmpty())revoke((UUID)rows.getFirst().get("session_id"));
    }
    @Transactional public boolean logoutAll(String raw) {
        if(!AuthStore.opaqueFormat(raw))return false;lock.acquire();
        var rows=store.jdbc.queryForList("SELECT s.* FROM "+store.table("auth_sessions")+" s JOIN "+store.table("auth_refresh_tokens")+" r ON r.session_id=s.session_id WHERE r.token_digest=? AND r.used_at IS NULL FOR UPDATE OF s",AuthStore.digest(raw));
        if(rows.isEmpty())return false;var row=rows.getFirst();TokenAccount account;
        try{account=accounts.forToken((UUID)row.get("user_id"));}catch(AccountAccessDeniedException ex){return false;}
        if(!valid(row,account))return false;
        var user=users.findById(account.userId()).orElseThrow();user.invalidateAuthorization();users.saveAndFlush(user);
        store.jdbc.update("UPDATE "+store.table("auth_sessions")+" SET revoked_at=COALESCE(revoked_at,?) WHERE user_id=?",Timestamp.from(clock.now()),user.getUserId());return true;
    }
}
