package com.paymesh.backend.security.auth;
import com.paymesh.backend.security.accounts.PersistentSessions;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestController
@ConditionalOnWebApplication(type=ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/auth")
public class SessionController {
    private final PersistentSessions sessions;private final JwtTokenService tokens;private final AuthBrowserPolicy browser;
    public SessionController(PersistentSessions sessions,JwtTokenService tokens,AuthBrowserPolicy browser){this.sessions=sessions;this.tokens=tokens;this.browser=browser;}
    @PostMapping("/refresh") public ResponseEntity<?> refresh(HttpServletRequest request) {
        if(!browser.allowed(request))return result(403,"Request denied",null);
        var grant=sessions.refresh(browser.token(request));if(grant==null)return result(401,"Authentication required",browser.clear());
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).header("Pragma","no-cache").header("Set-Cookie",browser.cookie(grant.refreshToken(),grant.rememberMe(),grant.expiresAt())).body(tokens.issue(grant.account(),grant.sessionId()));
    }
    @PostMapping("/logout") public ResponseEntity<?> logout(HttpServletRequest request) {
        if(!browser.allowed(request))return result(403,"Request denied",null);sessions.logout(browser.token(request));return result(200,"Signed out",browser.clear());
    }
    @PostMapping("/logout-all") public ResponseEntity<?> all(HttpServletRequest request) {
        if(!browser.allowed(request))return result(403,"Request denied",null);boolean done=sessions.logoutAll(browser.token(request));return result(done?200:401,done?"Signed out on all devices":"Authentication required",browser.clear());
    }
    private ResponseEntity<?> result(int code,String message,String cookie){var builder=ResponseEntity.status(code).cacheControl(CacheControl.noStore()).header("Pragma","no-cache");if(cookie!=null)builder.header("Set-Cookie",cookie);return builder.body(Map.of("status",code,"message",message));}
}
