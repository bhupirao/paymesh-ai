package com.paymesh.backend.security.accounts;

public class AccountAccessDeniedException extends RuntimeException {
    public AccountAccessDeniedException() { super("Account authentication or authorization failed"); }
}
