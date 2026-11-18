package com.paymesh.backend.security.auth;

import jakarta.servlet.http.HttpServletRequest;
import java.time.*;
import java.net.URI;
import java.util.*;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import org.springframework.http.ResponseCookie;

/** Fixed reviewed Origin + non-simple CSRF header; never trusts forwarded headers. */
@Component
public class AuthBrowserPolicy {
    public static final String COOKIE="pm_refresh";
    private final String origin;private final boolean secure;
    public AuthBrowserPolicy(Environment env) {
        origin=env.getProperty("paymesh.sessions.origin","");boolean local=env.getProperty("paymesh.sessions.local-http",Boolean.class,false);secure=!local;
        if(local) {
            boolean profile=Arrays.stream(env.getActiveProfiles()).anyMatch(p->p.equals("demo")||p.equals("development"));
            if(!profile||!"127.0.0.1".equals(env.getProperty("server.address"))||!"18080".equals(env.getProperty("server.port"))||!"http://127.0.0.1:5500".equals(origin))throw new IllegalStateException("Unsafe local session cookie configuration");
        } else if(!origin.isBlank()) {
            URI uri=URI.create(origin);if(!"https".equals(uri.getScheme())||uri.getHost()==null||!origin.equals(uri.getScheme()+"://"+uri.getRawAuthority()))throw new IllegalStateException("HTTPS origin required");
        }
    }
    public boolean browserRequest(HttpServletRequest request) {return request.getHeader("Origin")!=null;}
    public boolean allowed(HttpServletRequest request) {
        return !origin.isBlank()&&Collections.list(request.getHeaders("Origin")).equals(List.of(origin))&&"1".equals(request.getHeader("X-PayMesh-CSRF"))
            &&!"cross-site".equals(request.getHeader("Sec-Fetch-Site"));
    }
    public String cookie(String raw,boolean remember,Instant expires) {
        var b=ResponseCookie.from(COOKIE,raw).httpOnly(true).secure(secure).sameSite("Strict").path("/api/v1/auth");
        if(remember)b.maxAge(Duration.between(Instant.now(),expires).isNegative()?Duration.ZERO:Duration.between(Instant.now(),expires));return b.build().toString();
    }
    public String clear(){return ResponseCookie.from(COOKIE,"").httpOnly(true).secure(secure).sameSite("Strict").path("/api/v1/auth").maxAge(0).build().toString();}
    public String token(HttpServletRequest request){
        var cookies=request.getCookies();if(cookies==null)return null;String value=null;
        for(var cookie:cookies)if(COOKIE.equals(cookie.getName())){if(value!=null)return null;value=cookie.getValue();}return value;
    }
}
