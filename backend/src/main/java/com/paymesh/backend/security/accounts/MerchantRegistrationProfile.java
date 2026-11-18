package com.paymesh.backend.security.accounts;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

/** Registration PII is never serialized by a public controller. */
@Entity
@Table(name="merchant_registrations")
class MerchantRegistrationProfile {
    @Id @Column(name="user_id") private UUID userId;
    @Column(name="merchant_id",nullable=false,length=100) private String merchantId;
    @Column(name="first_name",nullable=false,length=80) private String firstName;
    @Column(name="last_name",nullable=false,length=80) private String lastName;
    @Column(name="business_name",nullable=false,length=160) private String businessName;
    @Column(nullable=false,length=254) private String email;
    @Column(nullable=false,length=16) private String mobile;
    @Column(name="business_type",nullable=false,length=24) private String businessType;
    @Column(nullable=false,length=5) private String country;
    @Column(name="terms_version",nullable=false,length=32) private String termsVersion;
    @Column(name="terms_accepted_at",nullable=false) private Instant termsAcceptedAt;
    protected MerchantRegistrationProfile() {}
    MerchantRegistrationProfile(UUID user, String merchant, String normalizedEmail, MerchantRegistration.Input input) {
        userId=user;merchantId=merchant;email=normalizedEmail;
        firstName=input.firstName.strip();lastName=input.lastName.strip();businessName=input.businessName.strip();
        mobile=input.mobile;businessType=input.businessType;country=input.country;
        termsVersion="demo-2026-11";termsAcceptedAt=Instant.now();
    }
}
