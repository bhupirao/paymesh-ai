package com.paymesh.backend.security.auth;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.*;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.Base64;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

final class JwtKeyMaterial {
    final RSAPrivateKey privateKey;
    final RSAPublicKey publicKey;
    final String issuer;
    final String audience;
    final String keyId;

    JwtKeyMaterial(String privateFile, String publicFile, String issuer, String audience) {
        boolean absent = privateFile.isBlank() && publicFile.isBlank() && issuer.isBlank() && audience.isBlank();
        if (absent) {
            privateKey = null; publicKey = null; this.issuer = null; this.audience = null; keyId = null;
            return;
        }
        byte[] privateDer = null;
        try {
            if (privateFile.isBlank() || publicFile.isBlank() || !URI.create(issuer).isAbsolute()
                    || audience.isBlank() || audience.length() > 255 || audience.chars().anyMatch(Character::isWhitespace)) {
                throw new IllegalArgumentException();
            }
            KeyFactory factory = KeyFactory.getInstance("RSA");
            privateDer = readPem(privateFile, "PRIVATE KEY");
            privateKey = (RSAPrivateKey) factory.generatePrivate(new PKCS8EncodedKeySpec(privateDer));
            publicKey = (RSAPublicKey) factory.generatePublic(new X509EncodedKeySpec(readPem(publicFile, "PUBLIC KEY")));
            if (publicKey.getModulus().bitLength() < 2048 || !privateKey.getModulus().equals(publicKey.getModulus())) {
                throw new IllegalArgumentException();
            }
            byte[] challenge = new byte[32]; new SecureRandom().nextBytes(challenge);
            Signature proof = Signature.getInstance("SHA256withRSA");
            proof.initSign(privateKey); proof.update(challenge); byte[] signature = proof.sign();
            proof.initVerify(publicKey); proof.update(challenge);
            if (!proof.verify(signature)) throw new IllegalArgumentException();
            this.issuer = issuer; this.audience = audience;
            keyId = Base64.getUrlEncoder().withoutPadding().encodeToString(MessageDigest.getInstance("SHA-256").digest(publicKey.getEncoded()));
        } catch (Exception ex) {
            // Do not include PEM contents, credentials, paths or the original parser exception.
            throw new IllegalStateException("Invalid JWT key/issuer/audience configuration");
        } finally {
            if (privateDer != null) Arrays.fill(privateDer, (byte) 0);
        }
    }

    private byte[] readPem(String file, String type) throws Exception {
        Path path = Path.of(file);
        if (!Files.isRegularFile(path) || Files.size(path) > 65536) throw new IllegalArgumentException();
        byte[] bytes = Files.readAllBytes(path);
        try {
            String pem = new String(bytes, StandardCharsets.US_ASCII).strip();
            String header = "-----BEGIN " + type + "-----", footer = "-----END " + type + "-----";
            if (!pem.startsWith(header) || !pem.endsWith(footer)) throw new IllegalArgumentException();
            return Base64.getDecoder().decode(pem.substring(header.length(), pem.length() - footer.length()).replaceAll("\\s", ""));
        } finally { Arrays.fill(bytes, (byte) 0); }
    }

    boolean configured() { return privateKey != null; }
    void requireConfigured() {
        if (!configured()) throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Authentication is not configured");
    }
}
