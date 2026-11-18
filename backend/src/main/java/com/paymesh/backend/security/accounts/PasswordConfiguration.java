package com.paymesh.backend.security.accounts;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
public class PasswordConfiguration {
    @Bean
    public PasswordEncoder passwordEncoder(@Value("${paymesh.accounts.bcrypt-strength:12}") int strength) {
        if (strength < 10 || strength > 16) throw new IllegalArgumentException("BCrypt strength must be between 10 and 16");
        return new BCryptPasswordEncoder(strength);
    }
}
