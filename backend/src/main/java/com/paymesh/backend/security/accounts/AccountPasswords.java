package com.paymesh.backend.security.accounts;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AccountPasswords {
    private final PasswordEncoder encoder;
    public AccountPasswords(PasswordEncoder encoder) { this.encoder = encoder; }

    public String hash(char[] password) {
        validate(password);
        return encoder.encode(CharBuffer.wrap(password));
    }

    public boolean matches(char[] password, String hash) {
        try {
            validate(password);
            return encoder.matches(CharBuffer.wrap(password), hash);
        } catch (IllegalArgumentException ex) { return false; }
    }

    public static void validate(char[] password) {
        if (password == null || password.length > 72 || Character.codePointCount(password, 0, password.length) < 12) {
            throw new IllegalArgumentException("Password must contain at least 12 characters and at most 72 UTF-8 bytes");
        }
        for (char c : password) if (c == 0) throw new IllegalArgumentException("Password cannot contain NUL");
        ByteBuffer bytes = null;
        try {
            // Reject malformed UTF-16 instead of allowing replacement-character collisions.
            bytes = StandardCharsets.UTF_8.newEncoder().encode(CharBuffer.wrap(password));
            if (bytes.remaining() > 72) throw new IllegalArgumentException("Password exceeds 72 UTF-8 bytes");
        } catch (CharacterCodingException ex) {
            throw new IllegalArgumentException("Password contains malformed Unicode");
        } finally {
            if (bytes != null && bytes.hasArray()) Arrays.fill(bytes.array(), (byte) 0);
        }
    }
}
