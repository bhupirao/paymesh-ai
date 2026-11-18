package com.paymesh.backend.security.business;

import com.paymesh.backend.entity.Payment;
import com.paymesh.backend.exception.PaymentNotFoundException;
import com.paymesh.backend.repository.*;
import com.paymesh.backend.security.accounts.*;
import com.paymesh.backend.security.SecurityStateUnavailableException;
import jakarta.persistence.EntityManager;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.dao.DataAccessException;
import jakarta.persistence.PersistenceException;
import org.springframework.transaction.TransactionSystemException;
import org.springframework.security.authentication.AuthenticationCredentialsNotFoundException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(propagation = Propagation.MANDATORY)
public class BusinessAccess {
    private final EntityManager entityManager;
    private final AppUserRepository users;
    private final UserRoleRepository roles;
    private final MerchantRepository merchants;
    private final PaymentRepository payments;
    private final AccountAudit audit;

    public BusinessAccess(EntityManager entityManager, AppUserRepository users, UserRoleRepository roles,
                          MerchantRepository merchants, PaymentRepository payments, AccountAudit audit) {
        this.entityManager = entityManager; this.users = users; this.roles = roles;
        this.merchants = merchants; this.payments = payments; this.audit = audit;
    }

    public Actor actor() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        if (!(authentication instanceof JwtAuthenticationToken token) || !token.isAuthenticated()) {
            throw new AuthenticationCredentialsNotFoundException("Authentication failed");
        }
        // Shared side of Phase 2's exclusive administration lock. Keep revocation,
        // verification and account changes from racing a financial authorization/mutation.
        try {
            entityManager.createNativeQuery("SELECT pg_advisory_xact_lock_shared(hashtextextended('paymesh:account-administration', 0))")
                    .getSingleResult();
            var jwt = token.getToken();
            if (jwt.getExpiresAt() == null || !jwt.getExpiresAt().isAfter(Instant.now())
                    || jwt.getNotBefore() == null || jwt.getNotBefore().isAfter(Instant.now())) throw new IllegalArgumentException();
            UUID id = UUID.fromString(jwt.getSubject());
            AppUser user = users.findById(id).filter(AppUser::isEnabled).orElseThrow(IllegalArgumentException::new);
            Object raw = jwt.getClaim("authorization_version");
            if (!(raw instanceof Number)) throw new IllegalArgumentException();
            long version = new BigDecimal(raw.toString()).toBigIntegerExact().longValueExact();
            if (version != user.getAuthorizationVersion()) throw new IllegalArgumentException();
            Set<AccountRole> current = roles.roles(id).stream().map(AccountRole::valueOf).collect(Collectors.toSet());
            Set<AccountRole> claimed = jwt.getClaimAsStringList("roles").stream().map(AccountRole::valueOf).collect(Collectors.toSet());
            if (!current.equals(claimed)) throw new IllegalArgumentException();
            if (!"ACTIVE".equals(user.getAccountStatus()) || current.isEmpty()) throw new AccessDeniedException("Access denied");
            return new Actor(user, current.contains(AccountRole.ADMIN), current.contains(AccountRole.MERCHANT));
        } catch (AccessDeniedException ex) { throw ex; }
        catch (DataAccessException ex) { throw new SecurityStateUnavailableException(); }
        catch (PersistenceException | TransactionSystemException ex) { throw new SecurityStateUnavailableException(); }
        catch (SecurityStateUnavailableException ex) { throw ex; }
        catch (RuntimeException ex) { throw new BadCredentialsException("Authentication failed"); }
    }

    public Payment payment(Actor actor, UUID paymentId, boolean lock) {
        return (lock ? payments.findAccessibleForUpdate(paymentId, actor.id(), actor.version(), actor.admin(), actor.merchant())
                : payments.findAccessibleById(paymentId, actor.id(), actor.version(), actor.admin(), actor.merchant()))
                .orElseThrow(() -> new PaymentNotFoundException(paymentId));
    }

    public void creation(Actor actor, String merchantId) {
        if (merchantId == null) throw new AccessDeniedException("Access denied");
        if (actor.admin() && !merchants.existsById(merchantId)) throw new BusinessResourceNotFoundException();
        if (merchants.countAccessibleForCreation(merchantId, actor.id(), actor.version(), actor.admin(), actor.merchant()) != 1) {
            throw new AccessDeniedException("Access denied");
        }
    }

    public void audit(Actor actor, String merchantId, UUID paymentId, String operation) {
        if (actor.admin()) audit.success(actor.user, operation, merchantId, "PAYMENT", paymentId.toString(), Map.of());
    }

    public static final class Actor {
        private final AppUser user;
        private final boolean admin;
        private final boolean merchant;
        private Actor(AppUser user, boolean admin, boolean merchant) { this.user = user; this.admin = admin; this.merchant = merchant; }
        public UUID id() { return user.getUserId(); }
        public long version() { return user.getAuthorizationVersion(); }
        public boolean admin() { return admin; }
        public boolean merchant() { return merchant; }
    }
}
