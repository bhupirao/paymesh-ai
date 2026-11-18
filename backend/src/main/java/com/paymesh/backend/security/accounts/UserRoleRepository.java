package com.paymesh.backend.security.accounts;

import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface UserRoleRepository extends JpaRepository<UserRole, UserRole.Id> {
    boolean existsByIdUserIdAndIdRoleName(UUID userId, String roleName);
    boolean existsByIdRoleName(String roleName);
    @Query("select r.id.roleName from SecurityUserRole r where r.id.userId = :userId")
    List<String> roles(@Param("userId") UUID userId);
    @Query("select count(r) from SecurityUserRole r, SecurityUser u "
            + "where u.userId = r.id.userId and u.enabled = true and r.id.roleName = 'ADMIN'")
    long countEnabledAdmins();
}
