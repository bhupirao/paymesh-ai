package com.paymesh.backend.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
class HealthReadinessIntegrationTest {
    @Autowired MockMvc mvc;
    @Autowired Environment environment;

    @Test
    void legacyPaymentAndActuatorHealthPathsRemainPublicWithoutComponentDetails() throws Exception {
        mvc.perform(get("/api/v1/payments/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("RUNNING"));

        for (String path : new String[]{"/actuator/health", "/actuator/health/liveness", "/actuator/health/readiness"}) {
            mvc.perform(get(path))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.status").value("UP"))
                    .andExpect(jsonPath("$.components").doesNotExist());
        }
    }

    @Test
    void livenessDoesNotIncludeDatabaseWhileReadinessRequiresIt() {
        assertEquals("livenessState", environment.getProperty("management.endpoint.health.group.liveness.include"));
        assertEquals("readinessState,db", environment.getProperty("management.endpoint.health.group.readiness.include"));
        assertEquals("true", environment.getProperty("management.endpoint.health.probes.enabled"));
        assertEquals("never", environment.getProperty("management.endpoint.health.show-details"));
        assertEquals("never", environment.getProperty("management.endpoint.health.show-components"));
    }

    @Test
    void actuatorDiscoveryAndInfoRemainAdminOnlyAndSensitiveEndpointsStayClosed() throws Exception {
        mvc.perform(get("/actuator")).andExpect(status().isUnauthorized());
        mvc.perform(get("/actuator/info")).andExpect(status().isUnauthorized());

        mvc.perform(get("/actuator").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_MERCHANT"))))
                .andExpect(status().isForbidden());
        mvc.perform(get("/actuator/info").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_MERCHANT"))))
                .andExpect(status().isForbidden());
        mvc.perform(get("/actuator").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_ADMIN"))))
                .andExpect(status().isOk());
        mvc.perform(get("/actuator/info").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_ADMIN"))))
                .andExpect(status().isOk());

        mvc.perform(get("/actuator/env"))
                .andExpect(result -> assertTrue(result.getResponse().getStatus() == 401
                        || result.getResponse().getStatus() == 403));
    }
}
