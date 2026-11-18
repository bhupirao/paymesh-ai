package com.paymesh.backend.security.auth;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {"paymesh.jwt.private-key-file=", "paymesh.jwt.public-key-file=",
        "paymesh.jwt.issuer=", "paymesh.jwt.audience="})
@AutoConfigureMockMvc
class JwtDisabledConfigurationIntegrationTest {
    @Autowired MockMvc mvc;
    @Test
    void missingKeysDisableLoginWithoutBlockingHealthOrRegistrationValidation() throws Exception {
        mvc.perform(post("/api/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("{\"login\":\"unconfigured.user\",\"password\":\"" + UUID.randomUUID() + "\"}"))
                .andExpect(status().isServiceUnavailable());
        mvc.perform(get("/api/v1/payments/health")).andExpect(status().isOk());
        mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest());
        mvc.perform(get("/api/v1/auth/unknown").header("Authorization", "Bearer invalid"))
                .andExpect(status().isUnauthorized());
    }
}
