package com.paymesh.backend.security.accounts;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Map;
import java.util.Properties;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class DemoDatabaseGuardTest {
    @Test
    void acceptsOnlyLocalPaymeshDemoJdbcTargets() {
        assertEquals("jdbc:postgresql://127.0.0.1:5432/paymesh_demo",
                DemoDatabaseGuard.validateConfiguredUrl("jdbc:postgresql://127.0.0.1:5432/paymesh_demo"));
        assertEquals("jdbc:postgresql://localhost/paymesh_demo",
                DemoDatabaseGuard.validateConfiguredUrl("jdbc:postgresql://localhost/paymesh_demo"));
    }

    @Test
    void rejectsApplicationAndUnexpectedDatabaseTargets() {
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(null));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(" "));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://127.0.0.1:5432/paymesh_db"));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://127.0.0.1:5432/another_demo"));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://db.example.test:5432/paymesh_demo"));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://192.0.2.10:5432/paymesh_demo"));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://127.0.0.1:5432"));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://127.0.0.1:5432/paymesh_demo?currentSchema=public"));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateConfiguredUrl(
                "jdbc:postgresql://127.0.0.1:70000/paymesh_demo"));
    }

    @Test
    void verifiesConnectedJdbcUrlAndActualDatabaseNameForDemoRuntime() throws Exception {
        DataSource source = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        DatabaseMetaData metadata = mock(DatabaseMetaData.class);
        Statement statement = mock(Statement.class);
        ResultSet result = mock(ResultSet.class);
        when(source.getConnection()).thenReturn(connection);
        when(connection.getMetaData()).thenReturn(metadata);
        when(metadata.getURL()).thenReturn("jdbc:postgresql://127.0.0.1:5432/paymesh_demo");
        when(connection.createStatement()).thenReturn(statement);
        when(statement.executeQuery("SELECT current_database()")).thenReturn(result);
        when(result.next()).thenReturn(true);
        when(result.getString(1)).thenReturn("paymesh_demo");
        DemoDatabaseGuard.verifyConnectedDatabase(source, "jdbc:postgresql://127.0.0.1:5432/paymesh_demo");

        when(result.getString(1)).thenReturn("paymesh_db");
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.verifyConnectedDatabase(
                source, "jdbc:postgresql://127.0.0.1:5432/paymesh_demo"));

        when(result.getString(1)).thenReturn("paymesh_demo");
        when(metadata.getURL()).thenReturn("jdbc:postgresql://127.0.0.1:5432/paymesh_db");
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.verifyConnectedDatabase(
                source, "jdbc:postgresql://127.0.0.1:5432/paymesh_demo"));

        when(metadata.getURL()).thenReturn("jdbc:postgresql://127.0.0.1:5432/paymesh_demo");
    }

    @Test
    void offlineProvisionerRequiresPinnedDatasourceAndExpectedDatabaseUser() throws Exception {
        DataSource unexpectedSource = mock(DataSource.class);
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.verifyOfflineProvisionerDatabase(
                unexpectedSource, "jdbc:postgresql://127.0.0.1:5432/paymesh_demo"));
        verifyNoInteractions(unexpectedSource);

        DriverManagerDataSource source = mock(DriverManagerDataSource.class);
        Connection connection = mock(Connection.class);
        DatabaseMetaData metadata = mock(DatabaseMetaData.class);
        Statement statement = mock(Statement.class);
        ResultSet result = mock(ResultSet.class);
        when(source.getConnection()).thenReturn(connection);
        when(connection.getMetaData()).thenReturn(metadata);
        when(metadata.getURL()).thenReturn("jdbc:postgresql://127.0.0.1:5432/paymesh_demo");
        when(metadata.getUserName()).thenReturn("paymesh_demo_user");
        when(connection.createStatement()).thenReturn(statement);
        when(statement.executeQuery("SELECT current_database()")).thenReturn(result);
        when(result.next()).thenReturn(true);
        when(result.getString(1)).thenReturn("paymesh_demo");
        DemoDatabaseGuard.verifyOfflineProvisionerDatabase(source, "jdbc:postgresql://127.0.0.1:5432/paymesh_demo");

        when(metadata.getUserName()).thenReturn("unexpected_user");
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.verifyOfflineProvisionerDatabase(
                source, "jdbc:postgresql://127.0.0.1:5432/paymesh_demo"));
    }

    @Test
    void rejectsConflictingDatasourceAndExternalSpringConfigurationOverrides() {
        String target = "jdbc:postgresql://127.0.0.1:5432/paymesh_demo";
        assertDoesNotThrow(() -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("PAYMESH_DB_URL", target,
                        "SPRING_DATASOURCE_URL", target,
                        "SPRING_DATASOURCE_USERNAME", "paymesh_demo_user",
                        "SPRING_DATASOURCE_TYPE", "org.springframework.jdbc.datasource.DriverManagerDataSource",
                        "SPRING_CONFIG_LOCATION", "classpath:/application.properties"), new Properties()));

        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("PAYMESH_DB_URL", "jdbc:postgresql://localhost:5432/paymesh_db"), new Properties()));
        Properties conflictingSystemProperties = new Properties();
        conflictingSystemProperties.setProperty("spring.datasource.url", "jdbc:postgresql://localhost:5432/paymesh_db");
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(
                target, Map.of(), conflictingSystemProperties));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_DATASOURCE_JNDI_NAME", "java:comp/env/jdbc/untrusted"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_DATASOURCE_TYPE", "com.zaxxer.hikari.HikariDataSource"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_DATASOURCE_USERNAME", "unexpected-user"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_CONFIG_ADDITIONAL_LOCATION", "file:/tmp/untrusted/"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_CONFIG_LOCATION", "file:/tmp/untrusted/"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_DATASOURCE_HIKARI_JDBC_URL", "jdbc:postgresql://db:5432/other"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_APPLICATION_JSON", "{}"), new Properties()));
        assertThrows(IllegalStateException.class, () -> DemoDatabaseGuard.validateProvisionerConfiguration(target,
                Map.of("SPRING_DATASOURCE_PASSWORD", "configured-elsewhere"), new Properties()));
    }
}
