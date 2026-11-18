package com.paymesh.backend.security.accounts;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.*;
import java.util.*;
import jakarta.persistence.EntityManager;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Public input never chooses a role, merchant ID, enabled flag or approval state. */
@Service
public class MerchantRegistration {
    private final AppUserRepository users;
    private final MerchantRepository merchants;
    private final MerchantMembershipRepository memberships;
    private final UserRoleRepository roles;
    private final AccountPasswords passwords;
    private final EntityManager entityManager;
    public MerchantRegistration(AppUserRepository users, MerchantRepository merchants,
            MerchantMembershipRepository memberships, UserRoleRepository roles, AccountPasswords passwords, EntityManager entityManager) {
        this.users = users; this.merchants = merchants; this.memberships = memberships;
        this.roles = roles; this.passwords = passwords; this.entityManager = entityManager;
    }

    @Transactional
    public Result register(Input input) {
        String email = AccountCredentials.normalizeLogin(input.email);
        if (users.existsByLoginNormalized(email)) throw new DuplicateRegistration();
        if (!Arrays.equals(input.password, input.confirmPassword)) throw new IllegalArgumentException("Invalid registration");
        // Existing password policy: 12+ code points, max 72 UTF-8 bytes, no malformed Unicode or NUL.
        String hash = passwords.hash(input.password);
        AppUser user = new AppUser(email, hash); user.pendingApproval();
        users.saveAndFlush(user); // Database unique constraint closes concurrent-email races.
        String merchantId = "M_" + UUID.randomUUID();
        merchants.saveAndFlush(new Merchant(merchantId)); // unverified, inactive
        MerchantMembership membership = new MerchantMembership(user.getUserId(), merchantId, null);
        membership.revoke(); memberships.saveAndFlush(membership);
        roles.saveAndFlush(new UserRole(user.getUserId(), AccountRole.MERCHANT, null));
        entityManager.persist(new MerchantRegistrationProfile(user.getUserId(), merchantId, email, input));
        entityManager.flush();
        return new Result("PENDING_APPROVAL", "Your account has been created successfully. You can now sign in using your email and password.");
    }
    public record Result(String accountStatus, String message) {}
    public static class DuplicateRegistration extends RuntimeException {}
    @JsonIgnoreProperties(ignoreUnknown = false)
    public static class Input {
        @NotBlank @Size(max=80) public String firstName;
        @NotBlank @Size(max=80) public String lastName;
        @NotBlank @Size(max=160) public String businessName;
        @NotBlank @Size(max=254) @Email @Pattern(regexp="(?i)[a-z0-9][a-z0-9._+\\-]*@[a-z0-9][a-z0-9.\\-]*\\.[a-z]{2,}") public String email;
        @NotNull @Pattern(regexp="\\+?[0-9]{7,15}") public String mobile;
        @NotNull @Pattern(regexp="SOLE_PROPRIETOR|COMPANY|PARTNERSHIP|NONPROFIT|OTHER") public String businessType;
        @NotNull @Pattern(regexp="IN|US|GB|CA|AU|OTHER") public String country;
        @NotNull @Size(min=12,max=72) @JsonProperty(access=JsonProperty.Access.WRITE_ONLY) public char[] password;
        @NotNull @Size(min=12,max=72) @JsonProperty(access=JsonProperty.Access.WRITE_ONLY) public char[] confirmPassword;
        @NotNull @AssertTrue public Boolean terms;
    }
}
