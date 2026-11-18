package com.paymesh.backend.testing;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;
import org.springframework.core.env.MapPropertySource;

import static org.junit.jupiter.api.Assertions.*;

class IsolatedDatabaseGuardTest {
    @Test
    void rejectsApplicationDatabaseBeforeAnyConnectionOrMigration() {
        try (var context = new GenericApplicationContext()) {
            context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("test", Map.of(
                    "spring.datasource.url", "jdbc:postgresql://localhost:5432/paymesh_db",
                    "PAYMESH_TEST_DB_DATA_DIRECTORY", "/private/tmp/not-a-test-cluster")));
            assertThrows(IllegalStateException.class, () -> new IsolatedDatabaseGuard().initialize(context));
        }
    }

    @Test
    void rejectsPort5432EvenWithIsolatedDatabaseName() {
        try (var context = new GenericApplicationContext()) {
            context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("test", Map.of(
                    "spring.datasource.url", "jdbc:postgresql://127.0.0.1:5432/paymesh_isolated_test",
                    "PAYMESH_TEST_DB_DATA_DIRECTORY", "/private/tmp/not-a-test-cluster")));
            assertThrows(IllegalStateException.class, () -> new IsolatedDatabaseGuard().initialize(context));
        }
    }
}
