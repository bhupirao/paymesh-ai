package com.paymesh.backend.security.accounts;

import com.paymesh.backend.PaymeshBackendApplication;
import java.io.Console;
import java.util.Arrays;
import javax.sql.DataSource;
import org.springframework.boot.ApplicationContextFactory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

/** Explicit offline command. Never registered as an application runner or HTTP endpoint. */
public final class InitialAdminProvisioner {
    private InitialAdminProvisioner() {}

    public static void main(String[] args) {
        if (args.length != 0) throw new IllegalArgumentException("This command accepts no arguments; use the interactive console");
        Console console = System.console();
        if (console == null) throw new IllegalStateException("A secure interactive console is required; stdin/arguments/environment passwords are not accepted");
        String demoUrl = validatedTarget(System.getenv("PAYMESH_DEMO_DB_URL"), System.getenv(), System.getProperties());
        String databaseUser = System.getenv("PAYMESH_DB_USER");
        String databasePassword = System.getenv("PAYMESH_DB_PASSWORD");
        if (!"paymesh_demo_user".equals(databaseUser)) {
            throw new IllegalStateException("PAYMESH_DB_USER must be paymesh_demo_user for offline ADMIN provisioning");
        }
        if (databasePassword == null || databasePassword.isBlank()) {
            throw new IllegalStateException("PAYMESH_DB_PASSWORD must be configured in the environment");
        }
        boolean targetConfirmed = confirmedTarget(console.readLine(
                "Target database is the local paymesh_demo database. Type BOOTSTRAP ADMIN IN paymesh_demo to continue: "));
        if (!targetConfirmed) return;
        boolean bootstrapConfirmed = confirmedBootstrap(console.readLine("Type PROVISION INITIAL ADMIN to continue: "));
        if (!bootstrapConfirmed) return;
        String login = console.readLine("Initial ADMIN login: ");
        char[] password = console.readPassword("Password (at least 12 characters, at most 72 UTF-8 bytes): ");
        char[] confirmation = null;
        try {
            confirmation = console.readPassword("Confirm password: ");
            requireMatchingPasswords(password, confirmation);
            // Requires an already migrated V8 database; never starts HTTP, migrations or settlement scheduling.
            try (var context = offlineApplication(PaymeshBackendApplication.class).run(offlineArguments(demoUrl))) {
                AccountView account = provisionIfConfirmed(targetConfirmed && bootstrapConfirmed, demoUrl, context.getBean(DataSource.class),
                        context.getBean(InitialAdminBootstrap.class), login, password);
                console.printf("Initial ADMIN provisioned: %s%n", account.userId());
            }
        } finally {
            if (password != null) Arrays.fill(password, '\0');
            if (confirmation != null) Arrays.fill(confirmation, '\0');
        }
    }

    static SpringApplication offlineApplication(Class<?>... sources) {
        SpringApplication application = new SpringApplication(sources);
        application.setWebApplicationType(WebApplicationType.NONE);
        // Unlike spring.main properties, this factory cannot be rebound by external
        // configuration. Even a conflicting web type cannot create a server context.
        application.setApplicationContextFactory(
                ApplicationContextFactory.ofContextClass(AnnotationConfigApplicationContext.class));
        return application;
    }

    static String[] offlineArguments(String demoDatasourceUrl) {
        String safeUrl = DemoDatabaseGuard.validateConfiguredUrl(demoDatasourceUrl);
        String[] base = new String[]{"--spring.main.web-application-type=none", "--spring.flyway.enabled=false",
                "--spring.jpa.hibernate.ddl-auto=validate", "--paymesh.settlement.scheduling-enabled=false"};
        String[] pinnedDatasource = new String[]{
                "--spring.config.location=classpath:/application.properties",
                "--spring.datasource.type=org.springframework.jdbc.datasource.DriverManagerDataSource",
                "--spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.JndiDataSourceAutoConfiguration",
                "--spring.datasource.jndi-name=",
                "--spring.datasource.url=" + safeUrl,
                "--spring.datasource.username=paymesh_demo_user",
                "--spring.datasource.password=${PAYMESH_DB_PASSWORD}"};
        String[] arguments = Arrays.copyOf(base, base.length + pinnedDatasource.length);
        System.arraycopy(pinnedDatasource, 0, arguments, base.length, pinnedDatasource.length);
        return arguments;
    }

    static boolean confirmedTarget(String response) {
        return "BOOTSTRAP ADMIN IN paymesh_demo".equals(response);
    }

    static boolean confirmedBootstrap(String response) {
        return "PROVISION INITIAL ADMIN".equals(response);
    }

    static String validatedTarget(String configuredUrl, java.util.Map<String, String> environment,
                                  java.util.Properties systemProperties) {
        String target = DemoDatabaseGuard.validateConfiguredUrl(configuredUrl);
        DemoDatabaseGuard.validateProvisionerConfiguration(target, environment, systemProperties);
        return target;
    }

    static void requireMatchingPasswords(char[] password, char[] confirmation) {
        if (password == null || confirmation == null || !Arrays.equals(password, confirmation)) {
            throw new IllegalArgumentException("Password confirmation failed");
        }
    }

    static AccountView provisionAfterTargetVerification(String configuredUrl, DataSource dataSource,
                                                       InitialAdminBootstrap bootstrap,
                                                       String login, char[] password) {
        DemoDatabaseGuard.verifyOfflineProvisionerDatabase(dataSource, configuredUrl);
        return bootstrap.provision(login, password);
    }

    static AccountView provisionIfConfirmed(boolean confirmed, String configuredUrl, DataSource dataSource,
                                            InitialAdminBootstrap bootstrap, String login, char[] password) {
        if (!confirmed) return null;
        return provisionAfterTargetVerification(configuredUrl, dataSource, bootstrap, login, password);
    }
}
