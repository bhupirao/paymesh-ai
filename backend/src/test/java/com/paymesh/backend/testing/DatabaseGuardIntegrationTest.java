package com.paymesh.backend.testing;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class DatabaseGuardIntegrationTest {
    @Autowired Environment environment;

    @Test
    void springBootActuallyRanIsolationVerificationBeforeStarting() {
        assertEquals("true", environment.getProperty("paymesh.test.isolation-verified"));
    }
}
