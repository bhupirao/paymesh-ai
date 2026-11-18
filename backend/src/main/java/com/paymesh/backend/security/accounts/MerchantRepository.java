package com.paymesh.backend.security.accounts;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.UUID;
import com.paymesh.backend.security.business.BusinessScopePredicate;

public interface MerchantRepository extends JpaRepository<Merchant, String> {
    @Query("select count(targetMerchant) from SecurityMerchant targetMerchant "
            + "where targetMerchant.merchantId = :merchantId and targetMerchant.verified = true "
            + "and targetMerchant.active = true and " + BusinessScopePredicate.CREATION)
    long countAccessibleForCreation(@Param("merchantId") String merchantId, @Param("callerId") UUID callerId,
            @Param("authorizationVersion") long version, @Param("admin") boolean admin, @Param("merchant") boolean merchant);
}
