package com.paymesh.backend.settlement;

public enum Observation {
    SUCCESS, FAILED, TIMEOUT, UNKNOWN;

    public boolean terminal() {
        return this == SUCCESS || this == FAILED;
    }
}
