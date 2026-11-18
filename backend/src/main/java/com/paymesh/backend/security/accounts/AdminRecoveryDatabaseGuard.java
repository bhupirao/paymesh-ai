package com.paymesh.backend.security.accounts;

import java.util.Map;
import java.util.Properties;
import javax.sql.DataSource;

/** Deliberately stricter than the provisioning guard: one literal host/port/database. */
final class AdminRecoveryDatabaseGuard {
    static final String IDENTITY_QUERY = "SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()";
    static final class VerificationFailure extends IllegalStateException {
        VerificationFailure() { super("Recovery database connection or identity verification failed"); }
    }
    static final String TARGET = "jdbc:postgresql://127.0.0.1:5432/paymesh_demo";
    static void configuration(String mode, String target, String user, Map<String,String> env, Properties props) {
        if (!"RESET_EXISTING_ADMIN".equals(mode) || !TARGET.equals(target) || !"paymesh_demo_user".equals(user))
            throw new IllegalStateException("Recovery requires explicit mode and the exact demo target");
        for (String key : env.keySet()) {
            if (key.startsWith("SPRING_") || key.startsWith("LOGGING_") || key.startsWith("HIBERNATE_")
                    || java.util.Set.of("JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","_JAVA_OPTIONS").contains(key))
                throw new IllegalStateException("Recovery configuration conflict");
        }
        for (Object raw : props.keySet()) {
            String key=raw.toString();
            if (key.startsWith("logging.") || key.startsWith("spring.") || key.startsWith("hibernate."))
                throw new IllegalStateException("Recovery configuration conflict");
        }
        DemoDatabaseGuard.validateProvisionerConfiguration(target, env, props);
    }
    void verify(DataSource source) {
        try {
            DemoDatabaseGuard.verifyOfflineProvisionerDatabase(source, TARGET);
            try (var connection=source.getConnection(); var statement=connection.createStatement();
                 var row=statement.executeQuery(IDENTITY_QUERY)) {
                if (!row.next() || !"paymesh_demo".equals(row.getString(1)) || !"paymesh_demo_user".equals(row.getString(2))
                        || !"127.0.0.1".equals(row.getString(3)) || row.getInt(4)!=5432) throw new VerificationFailure();
            }
        } catch (RuntimeException | java.sql.SQLException ex) {
            // No raw JDBC messages/credentials or nested causes escape to the console.
            throw new VerificationFailure();
        }
    }
}
