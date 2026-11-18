package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.*;
import com.paymesh.backend.security.accounts.*;
import java.util.Arrays;
import java.util.Map;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

/** Bearer-only administration; no public signup and no cookie authority. */
@RestController
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
@RequestMapping("/api/v1/admin/accounts")
public class AdminAccountController {
    private final AccountAdministration administration;
    private final AccountCredentials credentials;
    private final ObjectReader reader;

    public AdminAccountController(AccountAdministration administration, AccountCredentials credentials, ObjectMapper json) {
        this.administration = administration;
        this.credentials = credentials;
        this.reader = json.readerFor(Input.class).with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                .with(DeserializationFeature.FAIL_ON_TRAILING_TOKENS).with(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<?> create(@RequestBody byte[] body) {
        Input input = null;
        try {
            input = reader.readValue(body);
            if (input == null || input.login == null || input.login.length() > 255
                    || input.password == null || input.confirmPassword == null
                    || !Arrays.equals(input.password, input.confirmPassword))
                return reply(400, "Check account fields and password confirmation.");
            AccountPasswords.validate(input.password);
            // The same policy is also enforced by the transactional hashing service.
            var account = administration.createAdminAccount(credentials.currentJwtAccount(), input.login, input.password);
            return ResponseEntity.status(201).cacheControl(CacheControl.noStore()).header("Pragma", "no-cache")
                    .body(Map.of("userId", account.userId(), "login", account.login(), "enabled", account.enabled(),
                            "accountStatus", "ACTIVE", "roles", account.roles()));
        } catch (java.io.IOException ex) {
            return reply(400, "Invalid account request.");
        } catch (IllegalArgumentException ex) {
            return reply(400, "Check account fields and password requirements.");
        } catch (AccountAccessDeniedException ex) {
            return reply(403, "Access denied.");
        } catch (AccountOperationException ex) {
            // Existing facade intentionally conflates invalid input and duplicate names.
            return reply(409, "Account could not be created. Check login and password requirements.");
        } catch (RuntimeException ex) {
            return reply(503, "Account creation could not be confirmed. Check authorized account state before retrying.");
        } finally {
            Arrays.fill(body, (byte) 0);
            if (input != null) {
                if (input.password != null) Arrays.fill(input.password, '\0');
                if (input.confirmPassword != null) Arrays.fill(input.confirmPassword, '\0');
            }
        }
    }

    @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)
    ResponseEntity<?> unreadable() { return reply(400, "Invalid account request."); }

    private ResponseEntity<?> reply(int status, String message) {
        return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).header("Pragma", "no-cache")
                .body(Map.of("status", status, "message", message));
    }

    public static class Input {
        public String login;
        @com.fasterxml.jackson.annotation.JsonProperty(access = com.fasterxml.jackson.annotation.JsonProperty.Access.WRITE_ONLY)
        public char[] password;
        @com.fasterxml.jackson.annotation.JsonProperty(access = com.fasterxml.jackson.annotation.JsonProperty.Access.WRITE_ONLY)
        public char[] confirmPassword;
    }
}
