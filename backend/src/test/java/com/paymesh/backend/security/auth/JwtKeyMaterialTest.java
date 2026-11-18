package com.paymesh.backend.security.auth;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.*;
import java.util.Base64;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.*;

class JwtKeyMaterialTest {
    @TempDir Path directory;

    static KeyPair pair(int bits) throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA"); generator.initialize(bits); return generator.generateKeyPair();
    }
    static void pem(Path path, String type, byte[] der) throws Exception {
        Files.writeString(path, "-----BEGIN " + type + "-----\n" + Base64.getMimeEncoder(64, new byte[]{'\n'}).encodeToString(der)
                + "\n-----END " + type + "-----\n");
    }

    @Test
    void keysAreRuntimeOnlyAndMissingConfigurationFailsClosed() {
        var absent = new JwtKeyMaterial("", "", "", "");
        assertFalse(absent.configured());
        assertEquals(503, assertThrows(ResponseStatusException.class, absent::requireConfigured).getStatusCode().value());
        assertThrows(IllegalStateException.class, () -> new JwtKeyMaterial("missing", "", "", ""));
    }

    @Test
    void validatesRsaSizeAndMatchingPairWithoutDisclosingPrivateKey() throws Exception {
        KeyPair good = pair(2048), other = pair(2048);
        Path privatePath = directory.resolve("private.pem"), publicPath = directory.resolve("public.pem");
        pem(privatePath, "PRIVATE KEY", good.getPrivate().getEncoded());
        pem(publicPath, "PUBLIC KEY", good.getPublic().getEncoded());
        assertTrue(new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), "https://issuer.test", "paymesh-api").configured());
        pem(publicPath, "PUBLIC KEY", other.getPublic().getEncoded());
        assertEquals("Invalid JWT key/issuer/audience configuration", assertThrows(IllegalStateException.class, () ->
                new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), "https://issuer.test", "paymesh-api")).getMessage());
        KeyPair weak = pair(1024);
        pem(privatePath, "PRIVATE KEY", weak.getPrivate().getEncoded()); pem(publicPath, "PUBLIC KEY", weak.getPublic().getEncoded());
        assertThrows(IllegalStateException.class, () -> new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), "https://issuer.test", "paymesh-api"));
    }
}
