package com.paymesh.backend.security.accounts;
import java.time.*;
import org.springframework.stereotype.Component;
/** Dedicated injectable clock for session/recovery expiry, independent of JWT configuration. */
@Component
public class AuthenticationClock { public Instant now(){return Instant.now();} }
