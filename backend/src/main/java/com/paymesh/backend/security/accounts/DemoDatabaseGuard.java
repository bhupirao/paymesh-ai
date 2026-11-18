package com.paymesh.backend.security.accounts;

import java.sql.SQLException;
import java.util.Map;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.sql.DataSource;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/** Fail-closed target guard for the offline merchant demo provisioner. */
final class DemoDatabaseGuard {
    private static final String EXPECTED_DATASOURCE_TYPE = "org.springframework.jdbc.datasource.DriverManagerDataSource";
    private static final String PINNED_CONFIG_LOCATION = "classpath:/application.properties";
    private static final Pattern TARGET = Pattern.compile(
            "^jdbc:postgresql://(localhost|127\\.0\\.0\\.1)(?::([0-9]{1,5}))?/paymesh_demo$");

    private DemoDatabaseGuard() {}

    static String validateConfiguredUrl(String url) {
        if (url == null || url.isBlank()) throw new IllegalStateException("PAYMESH_DEMO_DB_URL is required");
        Matcher matcher = TARGET.matcher(url);
        if (!matcher.matches()) {
            throw new IllegalStateException("Merchant provisioning is restricted to a local PostgreSQL paymesh_demo database");
        }
        if (matcher.group(2) != null) {
            int port;
            try { port = Integer.parseInt(matcher.group(2)); }
            catch (NumberFormatException ex) { throw new IllegalStateException("Invalid demo database port"); }
            if (port < 1 || port > 65535) throw new IllegalStateException("Invalid demo database port");
        }
        return url;
    }

    static void validateProvisionerConfiguration(String targetUrl, Map<String, String> environment,
                                                Properties systemProperties) {
        String expectedUrl = validateConfiguredUrl(targetUrl);
        Map<String, String> env = environment == null ? Map.of() : environment;
        Properties props = systemProperties == null ? new Properties() : systemProperties;

        requireAbsentOrEqual(env.get("PAYMESH_DB_URL"), expectedUrl, "PAYMESH_DB_URL");
        requireAbsentOrEqual(env.get("SPRING_DATASOURCE_URL"), expectedUrl, "SPRING_DATASOURCE_URL");
        requireAbsentOrEqual(props.getProperty("spring.datasource.url"), expectedUrl, "spring.datasource.url");
        requireAbsentOrEqual(env.get("SPRING_DATASOURCE_USERNAME"), "paymesh_demo_user", "SPRING_DATASOURCE_USERNAME");
        requireAbsentOrEqual(props.getProperty("spring.datasource.username"), "paymesh_demo_user", "spring.datasource.username");
        requireAbsentOrEqual(env.get("SPRING_DATASOURCE_TYPE"), EXPECTED_DATASOURCE_TYPE, "SPRING_DATASOURCE_TYPE");
        requireAbsentOrEqual(props.getProperty("spring.datasource.type"), EXPECTED_DATASOURCE_TYPE, "spring.datasource.type");
        rejectNonBlank(env.get("SPRING_DATASOURCE_JNDI_NAME"), "SPRING_DATASOURCE_JNDI_NAME");
        rejectNonBlank(props.getProperty("spring.datasource.jndi-name"), "spring.datasource.jndi-name");
        rejectNonBlank(env.get("SPRING_DATASOURCE_PASSWORD"), "SPRING_DATASOURCE_PASSWORD");
        rejectNonBlank(props.getProperty("spring.datasource.password"), "spring.datasource.password");
        requireAbsentOrEqual(env.get("SPRING_CONFIG_LOCATION"), PINNED_CONFIG_LOCATION, "SPRING_CONFIG_LOCATION");
        requireAbsentOrEqual(props.getProperty("spring.config.location"), PINNED_CONFIG_LOCATION, "spring.config.location");
        rejectNonBlank(env.get("SPRING_CONFIG_ADDITIONAL_LOCATION"), "SPRING_CONFIG_ADDITIONAL_LOCATION");
        rejectNonBlank(props.getProperty("spring.config.additional-location"), "spring.config.additional-location");
        rejectNonBlank(env.get("SPRING_CONFIG_IMPORT"), "SPRING_CONFIG_IMPORT");
        rejectNonBlank(props.getProperty("spring.config.import"), "spring.config.import");
        rejectNonBlank(env.get("SPRING_APPLICATION_JSON"), "SPRING_APPLICATION_JSON");
        rejectNonBlank(props.getProperty("spring.application.json"), "spring.application.json");
        for (var entry : env.entrySet()) {
            String key = entry.getKey();
            if (key.startsWith("SPRING_DATASOURCE_") && !Map.of(
                    "SPRING_DATASOURCE_URL", true,
                    "SPRING_DATASOURCE_USERNAME", true,
                    "SPRING_DATASOURCE_TYPE", true,
                    "SPRING_DATASOURCE_JNDI_NAME", true,
                    "SPRING_DATASOURCE_PASSWORD", true).containsKey(key)) {
                rejectNonBlank(entry.getValue(), key);
            }
        }
        for (var entry : props.entrySet()) {
            String key = entry.getKey().toString();
            if (key.startsWith("spring.datasource.") && !Map.of(
                    "spring.datasource.url", true,
                    "spring.datasource.username", true,
                    "spring.datasource.type", true,
                    "spring.datasource.jndi-name", true,
                    "spring.datasource.password", true).containsKey(key)) {
                rejectNonBlank(entry.getValue().toString(), key);
            }
        }
    }

    private static void requireAbsentOrEqual(String configured, String expected, String setting) {
        if (configured != null && !configured.isBlank() && !expected.equals(configured)) {
            throw new IllegalStateException("Conflicting datasource/configuration override: " + setting);
        }
    }

    private static void rejectNonBlank(String configured, String setting) {
        if (configured != null && !configured.isBlank()) {
            throw new IllegalStateException("Conflicting datasource/configuration override: " + setting);
        }
    }

    static void verifyConnectedDatabase(DataSource dataSource, String configuredUrl) {
        String expected = validateConfiguredUrl(configuredUrl);
        verifyConnection(dataSource, expected, false);
    }

    static void verifyOfflineProvisionerDatabase(DataSource dataSource, String configuredUrl) {
        String expected = validateConfiguredUrl(configuredUrl);
        if (!(dataSource instanceof DriverManagerDataSource)) {
            throw new IllegalStateException("Offline provisioning requires the explicitly pinned DriverManagerDataSource");
        }
        verifyConnection(dataSource, expected, true);
    }

    private static void verifyConnection(DataSource dataSource, String expected, boolean verifyUser) {
        try (var connection = dataSource.getConnection()) {
            String actualUrl = connection.getMetaData().getURL();
            if (!expected.equals(actualUrl)) {
                throw new IllegalStateException("Connected PostgreSQL URL does not match PAYMESH_DEMO_DB_URL");
            }
            if (verifyUser && !"paymesh_demo_user".equals(connection.getMetaData().getUserName())) {
                throw new IllegalStateException("Connected PostgreSQL user is not the expected demo database user");
            }
            try (var statement = connection.createStatement(); var result = statement.executeQuery("SELECT current_database()")) {
                if (!result.next() || !"paymesh_demo".equals(result.getString(1))) {
                    throw new IllegalStateException("Connected database is not paymesh_demo");
                }
            }
        } catch (SQLException ex) {
            throw new IllegalStateException("Unable to verify the connected demo database; refusing provisioning", ex);
        }
    }
}
