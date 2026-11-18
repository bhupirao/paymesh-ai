package com.paymesh.backend.security.accounts;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;

import static org.junit.jupiter.api.Assertions.*;

class AccountPasswordsTest {
    private final PasswordEncoder encoder = new PasswordConfiguration().passwordEncoder(10);
    private final AccountPasswords passwords = new AccountPasswords(encoder);

    @Test
    void bcryptIsSaltedAndVerifiesWithoutStoringPlaintext() {
        char[] password = UUID.randomUUID().toString().toCharArray();
        String first = passwords.hash(password);
        String second = passwords.hash(password);
        assertNotEquals(first, second);
        assertNotEquals(new String(password), first);
        assertTrue(first.startsWith("$2"));
        assertTrue(passwords.matches(password, first));
        assertTrue(encoder.matches(java.nio.CharBuffer.wrap(password), second));
        assertFalse(passwords.matches(UUID.randomUUID().toString().toCharArray(), first));
        assertFalse(passwords.matches(null, first));
    }

    @Test
    void passwordLimitsRejectTruncationNulAndMalformedUnicode() {
        assertThrows(IllegalArgumentException.class, () -> passwords.hash(new char[0]));
        assertThrows(IllegalArgumentException.class, () -> passwords.hash("short".toCharArray()));
        assertThrows(IllegalArgumentException.class, () -> passwords.hash("x".repeat(73).toCharArray()));
        assertThrows(IllegalArgumentException.class, () -> passwords.hash("é".repeat(37).toCharArray()));
        assertThrows(IllegalArgumentException.class, () -> passwords.hash(("x".repeat(12) + '\0').toCharArray()));
        assertThrows(IllegalArgumentException.class, () -> passwords.hash(("x".repeat(12) + '\uD800').toCharArray()));
        char[] maximum = "é".repeat(36).toCharArray();
        assertTrue(passwords.matches(maximum, passwords.hash(maximum)));
    }

    @Test
    void encoderRejectsUnsafeWorkFactorAndLoginNormalizationIsExplicit() {
        assertThrows(IllegalArgumentException.class, () -> new PasswordConfiguration().passwordEncoder(4));
        assertThrows(IllegalArgumentException.class, () -> new PasswordConfiguration().passwordEncoder(17));
        assertEquals("staff@example.com", AccountCredentials.normalizeLogin(" STAFF@EXAMPLE.COM "));
        assertThrows(IllegalArgumentException.class, () -> AccountCredentials.normalizeLogin(null));
        assertThrows(IllegalArgumentException.class, () -> AccountCredentials.normalizeLogin("éxample"));
    }

    @Test
    void bootstrapRejectsCommandLineCredentialsBeforeStartingSpring() {
        assertThrows(IllegalArgumentException.class, () -> InitialAdminProvisioner.main(new String[]{"--password=not-accepted"}));
        if (System.console() == null) assertThrows(IllegalStateException.class,
                () -> InitialAdminProvisioner.main(new String[0]));
        assertEquals(0, AccountCredentials.AuthenticatedAccount.class.getConstructors().length);
    }
}
