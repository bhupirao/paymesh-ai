package com.paymesh.backend.security.accounts;

import com.paymesh.backend.gateway.DemoGatewayTimeoutSimulator;
import com.paymesh.backend.gateway.GatewayResponse;
import com.paymesh.backend.gateway.GatewayStatus;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

class DemoGatewayFaultSimulationConfigurationTest {
    @Test
    void simulationIsAbsentByDefaultAndWithoutDemoProfile() {
        new ApplicationContextRunner()
                .withUserConfiguration(DemoGatewayFaultSimulationConfiguration.class)
                .withInitializer(context -> context.getEnvironment().setActiveProfiles("demo"))
                .run(context -> assertFalse(context.containsBean("demoGatewayTimeoutSimulator")));

        new ApplicationContextRunner()
                .withUserConfiguration(DemoGatewayFaultSimulationConfiguration.class)
                .withPropertyValues("paymesh.demo.gateway-timeout.enabled=true")
                .run(context -> assertFalse(context.containsBean("demoGatewayTimeoutSimulator")));
    }

    @Test
    void enabledSimulationFailsBeforeMigrationForApplicationOrUnexpectedDatabase() {
        new ApplicationContextRunner()
                .withUserConfiguration(DemoGatewayFaultSimulationConfiguration.class)
                .withInitializer(context -> context.getEnvironment().setActiveProfiles("demo"))
                .withPropertyValues(
                        "paymesh.demo.gateway-timeout.enabled=true",
                        "spring.datasource.url=jdbc:postgresql://127.0.0.1:5432/paymesh_db")
                .run(context -> {
                    Throwable failure = context.getStartupFailure();
                    assertNotNull(failure);
                    while (failure.getCause() != null) failure = failure.getCause();
                    assertTrue(failure instanceof IllegalStateException);
                    assertTrue(failure.getMessage().contains("restricted"));
                });
    }

    @Test
    void selectorOnlyTimesOutSuccessfulKnownMockGatewayResponses() {
        DemoGatewayTimeoutSimulator simulator = new DemoGatewayTimeoutSimulator();
        UUID transactionId = UUID.randomUUID();
        GatewayResponse actual = new GatewayResponse(transactionId, "MOCK_RAZORPAY", GatewayStatus.SUCCESS, null, null);

        GatewayResponse simulated = simulator.observe(DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID, actual);
        assertEquals(GatewayStatus.TIMEOUT, simulated.status());
        assertEquals(transactionId, simulated.gatewayTransactionId());
        assertEquals("MOCK_RAZORPAY", simulated.gatewayName());
        assertSame(actual, simulator.observe("ordinary-customer", actual));
        GatewayResponse failed = new GatewayResponse(transactionId, "MOCK_RAZORPAY", GatewayStatus.FAILED, "DECLINED", null);
        assertSame(failed, simulator.observe(DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID, failed));
        GatewayResponse noTransaction = new GatewayResponse(null, "MOCK_RAZORPAY", GatewayStatus.SUCCESS, null, null);
        assertSame(noTransaction, simulator.observe(DemoGatewayTimeoutSimulator.RESERVED_CUSTOMER_ID, noTransaction));
    }
}
