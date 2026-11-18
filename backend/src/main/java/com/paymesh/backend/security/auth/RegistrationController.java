package com.paymesh.backend.security.auth;

import com.paymesh.backend.security.accounts.MerchantRegistration;
import jakarta.validation.Valid;
import java.util.Arrays;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/auth/register")
public class RegistrationController {
    private final MerchantRegistration registration;
    public RegistrationController(MerchantRegistration registration) { this.registration = registration; }
    @PostMapping
    public ResponseEntity<?> register(@Valid @RequestBody MerchantRegistration.Input input) {
        try { return response(201, registration.register(input)); }
        catch (MerchantRegistration.DuplicateRegistration | DataIntegrityViolationException ex) {
            return response(409, Map.of("status",409,"message","Registration could not be completed. Sign in or use different details."));
        } catch (IllegalArgumentException ex) {
            return response(400, Map.of("status",400,"message","Check registration fields and password requirements."));
        } finally {
            if (input.password != null) Arrays.fill(input.password, '\0');
            if (input.confirmPassword != null) Arrays.fill(input.confirmPassword, '\0');
        }
    }
    private ResponseEntity<?> response(int status, Object body) {
        return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).header("Pragma","no-cache").body(body);
    }
}
