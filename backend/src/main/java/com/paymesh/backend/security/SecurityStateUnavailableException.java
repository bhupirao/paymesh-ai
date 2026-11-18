package com.paymesh.backend.security;

import org.springframework.security.authentication.AuthenticationServiceException;

/** Authentication state could not be checked because its backing service is unavailable. */
public final class SecurityStateUnavailableException extends AuthenticationServiceException {
    public SecurityStateUnavailableException() { super("Authentication state is temporarily unavailable"); }
}
