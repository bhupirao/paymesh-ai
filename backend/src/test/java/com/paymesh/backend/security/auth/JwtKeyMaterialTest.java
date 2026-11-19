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

    @Test
    void relativeContainerIssuerReproducesStartupFailureWithOtherwiseValidKeys() throws Exception {
        KeyPair good = pair(2048);
        Path privatePath = directory.resolve("private.pem"), publicPath = directory.resolve("public.pem");
        pem(privatePath, "PRIVATE KEY", good.getPrivate().getEncoded());
        pem(publicPath, "PUBLIC KEY", good.getPublic().getEncoded());
        assertEquals("Invalid JWT key/issuer/audience configuration", assertThrows(IllegalStateException.class, () ->
                new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), "paymesh-container", "paymesh-container-ui")).getMessage());
    }

    @Test
    void actualComposeJwtConfigurationPassesStrictKeyValidation() throws Exception {
        Path root = Path.of("").toAbsolutePath();
        while (root != null && !Files.isRegularFile(root.resolve("deploy/compose.yaml"))) root = root.getParent();
        assertNotNull(root, "Repository Compose configuration must exist");
        var lines = Files.readAllLines(root.resolve("deploy/compose.yaml"));
        java.util.function.Function<String,String> setting = key -> lines.stream().map(String::strip)
                .filter(line -> line.startsWith(key + ": ")).map(line -> line.substring(key.length() + 2)).findFirst().orElseThrow();
        String issuer = setting.apply("PAYMESH_JWT_ISSUER"), audience = setting.apply("PAYMESH_JWT_AUDIENCE");
        assertTrue(java.net.URI.create(issuer).isAbsolute(), "Container JWT issuer must be an absolute URI");
        assertEquals("/run/secrets/jwt_private", setting.apply("PAYMESH_JWT_PRIVATE_KEY_FILE"));
        assertEquals("/run/secrets/jwt_public", setting.apply("PAYMESH_JWT_PUBLIC_KEY_FILE"));
        KeyPair good = pair(2048);
        Path privatePath = directory.resolve("private.pem"), publicPath = directory.resolve("public.pem");
        pem(privatePath, "PRIVATE KEY", good.getPrivate().getEncoded());
        pem(publicPath, "PUBLIC KEY", good.getPublic().getEncoded());
        var configured = new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), issuer, audience);
        assertTrue(configured.configured());
        assertEquals(issuer, configured.issuer);
        assertEquals(audience, configured.audience);
        assertThrows(IllegalStateException.class, () -> new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), issuer, " "));
        assertThrows(IllegalStateException.class, () -> new JwtKeyMaterial(privatePath.toString(), publicPath.toString(), issuer, "invalid audience"));
    }

}
