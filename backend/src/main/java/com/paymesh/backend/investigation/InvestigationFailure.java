package com.paymesh.backend.investigation;

public class InvestigationFailure extends RuntimeException {
    private final int status;
    public InvestigationFailure(int status, String message) { super(message); this.status = status; }
    public int status() { return status; }
}
