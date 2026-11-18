package com.paymesh.backend.testing;

import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.util.Map;
import org.springframework.context.ApplicationContextInitializer;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.MapPropertySource;

/** Runs before datasource/Flyway beans are created, including for existing integration tests. */
public class IsolatedDatabaseGuard implements ApplicationContextInitializer<ConfigurableApplicationContext> {
    @Override
    public void initialize(ConfigurableApplicationContext context) {
        var env = context.getEnvironment();
        String directory = env.getProperty("PAYMESH_TEST_DB_DATA_DIRECTORY");
        String url = env.getProperty("spring.datasource.url", "");
        if (directory == null || !url.matches("jdbc:postgresql://127\\.0\\.0\\.1:[0-9]+/paymesh_isolated_[a-zA-Z0-9_]+")
                || url.contains(":5432/")) {
            throw new IllegalStateException("Integration tests require a verified isolated database; run scripts/test-isolated.sh");
        }
        try {
            Path expected = Path.of(directory).toRealPath();
            Path marker = expected.getParent().resolve(".paymesh-isolated-test");
            String database = url.substring(url.lastIndexOf('/') + 1);
            if (!Files.readString(marker).trim().equals(database)) throw new IllegalStateException("Invalid isolation marker");
            try (var connection = DriverManager.getConnection(url, env.getProperty("spring.datasource.username"),
                    env.getProperty("spring.datasource.password"));
                 var statement = connection.createStatement();
                 var result = statement.executeQuery("SELECT current_database(), current_setting('data_directory'), inet_server_port()")) {
                result.next();
                if (!database.equals(result.getString(1)) || !expected.equals(Path.of(result.getString(2)).toRealPath())
                        || result.getInt(3) == 5432) throw new IllegalStateException("Database isolation verification failed");
            }
            context.getEnvironment().getPropertySources().addFirst(new MapPropertySource("verifiedTestIsolation",
                    Map.of("paymesh.test.isolation-verified", "true")));
        } catch (Exception ex) {
            throw new IllegalStateException("Cannot verify isolated PostgreSQL; refusing to run integration tests", ex);
        }
    }
}
