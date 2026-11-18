package com.paymesh.backend.security.accounts;

import java.io.Console;
import java.util.Arrays;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.context.annotation.*;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/** Explicit local console command; no REST endpoint, component scan, application runner or authenticated actor. */
public final class AdminPasswordRecovery {
    private AdminPasswordRecovery() {}
    static boolean confirmed(String response) { return "RESET ADMIN PASSWORD IN paymesh_demo".equals(response); }
    enum Stage { CONFIGURATION, DATABASE, PASSWORD, CONTEXT, RESET, CLEANUP }
    static String failureMessage(Stage stage, RuntimeException failure) {
        if (failure instanceof AdminRecoveryDatabaseGuard.VerificationFailure) stage=Stage.DATABASE;
        return switch (stage) {
            case CONFIGURATION -> "Offline recovery configuration is invalid. No reset was attempted.";
            case DATABASE -> "Database connection or identity verification failed. No password reset was performed. Check the approved demo target and database credentials privately.";
            case PASSWORD -> "Password validation failed. Use matching passwords with at least 12 characters and at most 72 UTF-8 bytes, without NUL or malformed Unicode. No reset was attempted.";
            case CONTEXT -> "Offline Spring context initialization failed. No reset transaction was started. Check the existing schema and approved configuration privately.";
            case RESET -> "Reset transaction failed or commit could not be confirmed. No automatic retry. Verify account/audit state privately before retrying.";
            case CLEANUP -> "Password reset committed, but offline context cleanup failed. Do not repeat the reset automatically; verify account/audit state privately.";
        };
    }
    public static void main(String[] args) {
        if (args.length!=0) throw new IllegalArgumentException("Recovery accepts no command-line arguments");
        Console console=System.console();
        if (console==null) throw new IllegalStateException("Recovery requires an interactive terminal");
        char[] databasePassword=null,password=null,confirmation=null;
        DriverManagerDataSource source=null;
        boolean failed=false;
        Stage stage=Stage.CONFIGURATION;
        try {
            AdminRecoveryDatabaseGuard.configuration(System.getenv("PAYMESH_OFFLINE_ADMIN_RECOVERY"),
                    System.getenv("PAYMESH_DEMO_DB_URL"),System.getenv("PAYMESH_DB_USER"),System.getenv(),System.getProperties());
            if (!confirmed(console.readLine("Type RESET ADMIN PASSWORD IN paymesh_demo to continue: "))) {
                console.printf("Recovery cancelled; no changes made.%n");return;
            }
            String login=console.readLine("Existing ADMIN username: ");
            stage=Stage.DATABASE;
            databasePassword=console.readPassword("Demo database password (hidden): ");
            if (databasePassword==null || databasePassword.length==0) throw new IllegalArgumentException();
            source=new DriverManagerDataSource(AdminRecoveryDatabaseGuard.TARGET,"paymesh_demo_user",new String(databasePassword));
            new AdminRecoveryDatabaseGuard().verify(source); // Before JPA startup or any writes.
            stage=Stage.PASSWORD;
            password=console.readPassword("New ADMIN password (12+ characters, max 72 UTF-8 bytes): ");
            confirmation=console.readPassword("Confirm new ADMIN password: ");
            InitialAdminProvisioner.requireMatchingPasswords(password,confirmation);
            AccountPasswords.validate(password);
            stage=Stage.CONTEXT;
            var application=InitialAdminProvisioner.offlineApplication(RecoveryConfiguration.class);
            final DriverManagerDataSource pinned=source;
            application.addInitializers(context->context.getBeanFactory().registerSingleton("dataSource",pinned));
            try (var context=application.run(new String[]{
                    "--spring.config.location=classpath:/application.properties", "--spring.profiles.active=",
                    "--spring.main.web-application-type=none", "--spring.main.banner-mode=off",
                    "--spring.flyway.enabled=false", "--spring.sql.init.mode=never",
                    "--spring.jpa.hibernate.ddl-auto=validate", "--spring.jpa.properties.hibernate.hbm2ddl.auto=validate",
                    "--spring.jpa.properties.hibernate.default_schema=public", "--spring.jpa.show-sql=false",
                    "--spring.jpa.properties.hibernate.show_sql=false", "--spring.jpa.properties.hibernate.format_sql=false",
                    "--logging.level.root=OFF", "--logging.level.org.hibernate.SQL=OFF", "--logging.level.org.hibernate.orm.jdbc.bind=OFF",
                    "--logging.level.org.hibernate.type.descriptor.sql=OFF", "--paymesh.settlement.scheduling-enabled=false"})) {
                var recovery=context.getBean(AdminPasswordRecoveryTransaction.class);
                stage=Stage.RESET;
                recovery.reset(login,password,confirmation);
                stage=Stage.CLEANUP;
            }
            console.printf("Existing ADMIN password reset successfully; prior access tokens are invalidated.%n");
        } catch (RuntimeException ex) {
            failed=true;
            // Neither raw database exception text nor secret-bearing object representations may escape.
            console.printf("%s%n", failureMessage(stage,ex));
        } finally {
            if (source!=null) source.setPassword("");
            for (char[] value:new char[][]{databasePassword,password,confirmation}) if (value!=null) Arrays.fill(value,'\0');
        }
        if (failed) System.exit(1);
    }
    // Intentionally NOT @Configuration/@Component: normal application scanning must never load this context.
    @EnableAutoConfiguration(exclude={
        org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration.class,
        org.springframework.boot.autoconfigure.jdbc.JndiDataSourceAutoConfiguration.class,
        org.springframework.boot.autoconfigure.flyway.FlywayAutoConfiguration.class,
        org.springframework.boot.autoconfigure.sql.init.SqlInitializationAutoConfiguration.class,
        org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration.class})
    @EntityScan(basePackageClasses=AppUser.class)
    @EnableJpaRepositories(basePackageClasses=AppUserRepository.class)
    @Import({AccountPasswords.class,PasswordConfiguration.class,AccountAdministrationLock.class,AccountAudit.class,AdminPasswordRecoveryTransaction.class})
    static class RecoveryConfiguration {
        @Bean AdminRecoveryDatabaseGuard recoveryDatabaseGuard() { return new AdminRecoveryDatabaseGuard(); }
    }
}
