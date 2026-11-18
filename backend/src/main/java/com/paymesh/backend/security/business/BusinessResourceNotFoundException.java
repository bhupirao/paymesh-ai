package com.paymesh.backend.security.business;

public class BusinessResourceNotFoundException extends RuntimeException {
    public BusinessResourceNotFoundException() { super("Resource not found"); }
}
