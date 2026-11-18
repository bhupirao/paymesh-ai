package com.paymesh.backend.security.business;

/** Compile-time JPQL fragments: arguments are server-derived, never request role flags. */
public final class BusinessScopePredicate {
    private BusinessScopePredicate() {}
    private static final String ACCOUNT = "exists (select u.userId from SecurityUser u where u.userId = :callerId "
            + "and u.enabled = true and u.authorizationVersion = :authorizationVersion and (";
    private static final String ADMIN = "(:admin = true and exists (select ar.id.userId from SecurityUserRole ar "
            + "where ar.id.userId = u.userId and ar.id.roleName = 'ADMIN'))";
    private static final String MEMBER = "(:merchant = true and exists (select mr.id.userId from SecurityUserRole mr "
            + "where mr.id.userId = u.userId and mr.id.roleName = 'MERCHANT') "
            + "and exists (select mm.id.userId from SecurityMerchantMembership mm, SecurityMerchant registry "
            + "where mm.id.userId = u.userId and mm.active = true and registry.merchantId = mm.id.merchantId "
            + "and registry.verified = true and registry.active = true and mm.id.merchantId = ";
    public static final String PAYMENT = ACCOUNT + ADMIN + " or " + MEMBER + "p.merchantId))))";
    public static final String CREATION = ACCOUNT + ADMIN + " or " + MEMBER + "targetMerchant.merchantId))))";
}
