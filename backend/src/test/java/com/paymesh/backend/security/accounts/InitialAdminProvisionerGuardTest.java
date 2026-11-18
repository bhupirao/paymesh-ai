package com.paymesh.backend.security.accounts;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.Map;
import java.util.Properties;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class InitialAdminProvisionerGuardTest {
    private static final String DEMO_URL = "jdbc:postgresql://127.0.0.1:5432/paymesh_demo";

    @Test
    void rejectedTargetCannotReachDatasourceOrBootstrapWrites() {
        DriverManagerDataSource dataSource = mock(DriverManagerDataSource.class);
        InitialAdminBootstrap bootstrap = mock(InitialAdminBootstrap.class);

        assertThrows(IllegalStateException.class, () -> InitialAdminProvisioner.provisionIfConfirmed(
                true, "jdbc:postgresql://127.0.0.1:5432/paymesh_db", dataSource, bootstrap,
                "first.admin", "valid-password-123".toCharArray()));

        verifyNoInteractions(dataSource, bootstrap);
    }

    @Test
    void missingOrConflictingExplicitTargetIsRejectedBeforeDatabaseAccess() {
        DriverManagerDataSource dataSource = mock(DriverManagerDataSource.class);
        InitialAdminBootstrap bootstrap = mock(InitialAdminBootstrap.class);
        assertThrows(IllegalStateException.class, () -> InitialAdminProvisioner.validatedTarget(
                null, Map.of(), new Properties()));
        assertThrows(IllegalStateException.class, () -> InitialAdminProvisioner.validatedTarget(
                DEMO_URL, Map.of("PAYMESH_DB_URL", "jdbc:postgresql://localhost:5432/paymesh_db"), new Properties()));

        assertThrows(IllegalStateException.class, () -> InitialAdminProvisioner.provisionIfConfirmed(
                true, "jdbc:postgresql://127.0.0.1:5432/paymesh_db", dataSource, bootstrap,
                "first.admin", "valid-password-123".toCharArray()));
        verifyNoInteractions(dataSource, bootstrap);
    }

    @Test
    void explicitlyConfiguredLoopbackDemoTargetIsAccepted() {
        assertEquals(DEMO_URL, InitialAdminProvisioner.validatedTarget(DEMO_URL, Map.of(), new Properties()));
    }

    @Test
    void rejectedOperatorConfirmationCannotOpenConnectionOrWriteAccountOrAudit() {
        DriverManagerDataSource dataSource = mock(DriverManagerDataSource.class);
        InitialAdminBootstrap bootstrap = mock(InitialAdminBootstrap.class);

        AccountView result = InitialAdminProvisioner.provisionIfConfirmed(false, DEMO_URL, dataSource, bootstrap,
                "first.admin", "valid-password-123".toCharArray());

        assertNull(result);
        verifyNoInteractions(dataSource, bootstrap);
    }

    @Test
    void connectedTargetMismatchIsRejectedBeforeBootstrapWrites() throws Exception {
        DriverManagerDataSource dataSource = mock(DriverManagerDataSource.class);
        Connection connection = mock(Connection.class);
        DatabaseMetaData metadata = mock(DatabaseMetaData.class);
        Statement statement = mock(Statement.class);
        ResultSet result = mock(ResultSet.class);
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.getMetaData()).thenReturn(metadata);
        when(metadata.getURL()).thenReturn("jdbc:postgresql://127.0.0.1:5432/paymesh_demo");
        when(metadata.getUserName()).thenReturn("paymesh_demo_user");
        when(connection.createStatement()).thenReturn(statement);
        when(statement.executeQuery("SELECT current_database()")).thenReturn(result);
        when(result.next()).thenReturn(true);
        when(result.getString(1)).thenReturn("paymesh_db");
        InitialAdminBootstrap bootstrap = mock(InitialAdminBootstrap.class);

        assertThrows(IllegalStateException.class, () -> InitialAdminProvisioner.provisionIfConfirmed(
                true, DEMO_URL, dataSource, bootstrap, "first.admin", "valid-password-123".toCharArray()));

        verify(dataSource).getConnection();
        verify(bootstrap, never()).provision(anyString(), any(char[].class));
    }

    @Test
    void targetAndExistingBootstrapConfirmationsMustMatchExactly() {
        assertTrue(InitialAdminProvisioner.confirmedTarget("BOOTSTRAP ADMIN IN paymesh_demo"));
        assertFalse(InitialAdminProvisioner.confirmedTarget("BOOTSTRAP ADMIN IN paymesh_db"));
        assertFalse(InitialAdminProvisioner.confirmedTarget(""));
        assertTrue(InitialAdminProvisioner.confirmedBootstrap("PROVISION INITIAL ADMIN"));
        assertFalse(InitialAdminProvisioner.confirmedBootstrap("provision initial admin"));
    }

    @Test
    void matchingPasswordConfirmationIsRequiredAndNeverNormalized() {
        assertDoesNotThrow(() -> InitialAdminProvisioner.requireMatchingPasswords(
                "Valid-password-123".toCharArray(), "Valid-password-123".toCharArray()));
        assertThrows(IllegalArgumentException.class, () -> InitialAdminProvisioner.requireMatchingPasswords(
                "Valid-password-123".toCharArray(), "valid-password-123".toCharArray()));
        assertThrows(IllegalArgumentException.class, () -> InitialAdminProvisioner.requireMatchingPasswords(
                null, "Valid-password-123".toCharArray()));
    }
}
