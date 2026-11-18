package com.paymesh.backend.security.accounts;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AppUserRepository extends JpaRepository<AppUser, UUID> {
    Optional<AppUser> findByLoginNormalized(String loginNormalized);
    boolean existsByLoginNormalized(String loginNormalized);
}
