package com.paymesh.backend.security.accounts;

import org.springframework.data.jpa.repository.JpaRepository;

public interface MerchantMembershipRepository extends JpaRepository<MerchantMembership, MerchantMembership.Id> {}
