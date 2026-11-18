package com.paymesh.backend.security.accounts;

import java.nio.charset.StandardCharsets;
import java.security.*;
import java.time.*;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** Schema prefix comes only from reviewed server configuration, never request input. */
@Component
public class AuthStore {
    public final JdbcTemplate jdbc;
    private final String prefix;
    private final SecureRandom random=new SecureRandom();
    public AuthStore(JdbcTemplate jdbc, Environment env) {
        this.jdbc=jdbc;String schema=env.getProperty("spring.jpa.properties.hibernate.default_schema","public");
        if(!schema.matches("[a-zA-Z_][a-zA-Z0-9_]*")) throw new IllegalStateException("Invalid authentication schema");
        prefix='"'+schema+'"'+'.';
    }
    public String table(String name) { return prefix+name; }
    public String opaque() { byte[] bytes=new byte[32];random.nextBytes(bytes);return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes); }
    public String otp() {return String.format(Locale.ROOT,"%06d",random.nextInt(1_000_000));}
    public static String digest(String value) {
        try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}
        catch(GeneralSecurityException ex){throw new IllegalStateException("Digest unavailable");}
    }
    public static String keyed(String key,String value) {
        try {var mac=Mac.getInstance("HmacSHA256");mac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8),"HmacSHA256"));return HexFormat.of().formatHex(mac.doFinal(value.getBytes(StandardCharsets.UTF_8)));}
        catch(GeneralSecurityException ex){throw new IllegalStateException("Digest unavailable");}
    }
    public static boolean equal(String a,String b){return a!=null&&b!=null&&MessageDigest.isEqual(a.getBytes(StandardCharsets.US_ASCII),b.getBytes(StandardCharsets.US_ASCII));}
    public static boolean opaqueFormat(String value){return value!=null&&value.matches("[A-Za-z0-9_-]{43}");}
    public static Instant instant(Map<String,Object> row,String name){return ((java.sql.Timestamp)row.get(name)).toInstant();}
}
