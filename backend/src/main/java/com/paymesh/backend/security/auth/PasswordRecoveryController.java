package com.paymesh.backend.security.auth;
import com.paymesh.backend.security.accounts.LocalPasswordRecovery;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestController
@ConditionalOnWebApplication(type=ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/auth/password")
public class PasswordRecoveryController {
    private final LocalPasswordRecovery recovery;private final AuthBrowserPolicy browser;
    public PasswordRecoveryController(LocalPasswordRecovery recovery,AuthBrowserPolicy browser){this.recovery=recovery;this.browser=browser;}
    @GetMapping("/capabilities") public ResponseEntity<?> capabilities(){return reply(200,Map.of("localDemoEnabled",recovery.enabled()));}
    @PostMapping("/forgot") public ResponseEntity<?> forgot(@Valid @RequestBody Forgot input,HttpServletRequest req){return execute(req,()->reply(200,recovery.forgot(input.identity,input.portal,req.getRemoteAddr())));}
    @PostMapping("/verify-otp") public ResponseEntity<?> verify(@Valid @RequestBody Verify input,HttpServletRequest req){return execute(req,()->{String token=recovery.verify(input.challengeId,input.portal,input.otp,req.getRemoteAddr());return token==null?reply(400,Map.of("message","Invalid or expired recovery")):reply(200,Map.of("resetAuthorization",token,"expiresIn",300));});}
    @PostMapping("/reset") public ResponseEntity<?> reset(@Valid @RequestBody Reset input,HttpServletRequest req){try{return execute(req,()->{recovery.reset(input.challengeId,input.portal,input.resetAuthorization,input.password,input.confirmPassword,req.getRemoteAddr());return reply(200,Map.of("message","Password reset successful. Sign in with your new password."));});}finally{if(input.password!=null)Arrays.fill(input.password,'\0');if(input.confirmPassword!=null)Arrays.fill(input.confirmPassword,'\0');}}
    private ResponseEntity<?> execute(HttpServletRequest req,java.util.function.Supplier<ResponseEntity<?>> action){
        if(!recovery.enabled())return reply(404,Map.of("message","Recovery unavailable"));if(!"127.0.0.1".equals(req.getRemoteAddr())||!"127.0.0.1".equals(req.getLocalAddr())||req.getLocalPort()!=18080||req.getHeader("Forwarded")!=null||req.getHeader("X-Forwarded-For")!=null||!browser.allowed(req))return reply(403,Map.of("message","Request denied"));
        try{return action.get();}catch(LocalPasswordRecovery.Disabled ex){return reply(404,Map.of("message","Recovery unavailable"));}catch(LocalPasswordRecovery.Limited ex){return ResponseEntity.status(429).cacheControl(CacheControl.noStore()).header("Retry-After","60").body(Map.of("message","Wait before trying again"));}catch(LocalPasswordRecovery.Invalid|IllegalArgumentException ex){return reply(400,Map.of("message","Invalid or expired recovery. Check password requirements."));}
    }
    private ResponseEntity<?> reply(int code,Object body){return ResponseEntity.status(code).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(body);}
    public static class Forgot {@NotBlank @Size(max=255) public String identity;@NotNull @Pattern(regexp="ADMIN|MERCHANT") public String portal;}
    public static class Verify {@NotNull public UUID challengeId;@NotNull @Pattern(regexp="ADMIN|MERCHANT") public String portal;@NotNull @Pattern(regexp="[0-9]{6}") @JsonProperty(access=JsonProperty.Access.WRITE_ONLY) public String otp;}
    public static class Reset {@NotNull public UUID challengeId;@NotNull @Pattern(regexp="ADMIN|MERCHANT") public String portal;@NotNull @Size(max=100) @JsonProperty(access=JsonProperty.Access.WRITE_ONLY) public String resetAuthorization;@NotNull @Size(max=72) @JsonProperty(access=JsonProperty.Access.WRITE_ONLY) public char[] password;@NotNull @Size(max=72) @JsonProperty(access=JsonProperty.Access.WRITE_ONLY) public char[] confirmPassword;}
}
