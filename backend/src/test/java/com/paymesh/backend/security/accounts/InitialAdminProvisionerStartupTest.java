package com.paymesh.backend.security.accounts;

import java.util.Map;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.test.util.TestPropertyValues;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.web.context.WebServerApplicationContext;
import org.springframework.boot.web.server.WebServer;
import org.springframework.boot.web.servlet.ServletContextInitializer;
import org.springframework.boot.web.servlet.server.ServletWebServerFactory;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class InitialAdminProvisionerStartupTest {
    // No application scanning, repositories, bootstrap service or auto-configuration.
    // These tests exercise actual Boot startup without provisioning any account.
    @TestConfiguration(proxyBeanMethods = false)
    static class StartupProbe {
        @Bean
        ServletWebServerFactory serverFactory() { return mock(ServletWebServerFactory.class); }
    }

    @ParameterizedTest
    @ValueSource(strings = {"servlet", "reactive"})
    void fixedArgumentsOverrideConflictingEnvironmentConfiguration(String webType) {
        StandardEnvironment environment = new StandardEnvironment();
        environment.getPropertySources().addFirst(new SystemEnvironmentPropertySource("conflictingEnvironment",
                Map.of("SPRING_MAIN_WEB_APPLICATION_TYPE", webType,
                        "SPRING_FLYWAY_ENABLED", "true",
                        "SPRING_JPA_HIBERNATE_DDL_AUTO", "create-drop",
                        "PAYMESH_SETTLEMENT_SCHEDULING_ENABLED", "true")));
        SpringApplication application = application();
        application.setEnvironment(environment);
        try (var context = application.run(offlineArguments())) {
            assertNonWeb(context);
            assertSafetyProperties(context);
            assertEquals(WebApplicationType.NONE, application.getWebApplicationType());
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"servlet", "reactive"})
    void fixedArgumentsOverrideConflictingSystemProperties(String webType) {
        TestPropertyValues.of("spring.main.web-application-type=" + webType,
                "spring.flyway.enabled=true", "spring.jpa.hibernate.ddl-auto=create-drop",
                "paymesh.settlement.scheduling-enabled=true").applyToSystemProperties(() -> {
                    SpringApplication application = application();
                    try (var context = application.run(offlineArguments())) {
                        assertNonWeb(context);
                        assertSafetyProperties(context);
                        assertEquals(WebApplicationType.NONE, application.getWebApplicationType());
                    }
                });
    }

    @ParameterizedTest
    @ValueSource(strings = {"servlet", "reactive"})
    void contextFactoryCannotCreateServerContextEvenIfWebTypeIsRebound(String webType) {
        SpringApplication application = application();
        // Deliberately bypass the first safeguard in the test only. The factory
        // must remain non-web even after Boot successfully binds a conflicting type.
        String[] arguments = offlineArguments();
        arguments[0] = "--spring.main.web-application-type=" + webType;
        try (var context = application.run(arguments)) {
            assertEquals(WebApplicationType.valueOf(webType.toUpperCase(java.util.Locale.ROOT)),
                    application.getWebApplicationType());
            assertNonWeb(context);
        }
    }

    @org.junit.jupiter.api.Test
    void initialAdminArgumentsPinDemoDatabaseWithoutAcceptingOtherTargets() {
        String[] args = InitialAdminProvisioner.offlineArguments("jdbc:postgresql://127.0.0.1:5432/paymesh_demo");
        assertTrue(java.util.Arrays.asList(args).contains("--spring.datasource.url=jdbc:postgresql://127.0.0.1:5432/paymesh_demo"));
        assertTrue(java.util.Arrays.asList(args).contains("--spring.datasource.username=paymesh_demo_user"));
        assertTrue(java.util.Arrays.asList(args).contains("--spring.config.location=classpath:/application.properties"));
        assertTrue(java.util.Arrays.asList(args).contains(
                "--spring.datasource.type=org.springframework.jdbc.datasource.DriverManagerDataSource"));
        assertTrue(java.util.Arrays.asList(args).contains(
                "--spring.autoconfigure.exclude=org.springframework.boot.autoconfigure.jdbc.JndiDataSourceAutoConfiguration"));
        assertTrue(java.util.Arrays.asList(args).contains("--spring.datasource.jndi-name="));
        assertTrue(java.util.Arrays.asList(args).contains("--spring.main.web-application-type=none"));
        assertTrue(java.util.Arrays.asList(args).contains("--spring.flyway.enabled=false"));
        assertTrue(java.util.Arrays.asList(args).contains("--spring.jpa.hibernate.ddl-auto=validate"));
        assertTrue(java.util.Arrays.asList(args).contains("--paymesh.settlement.scheduling-enabled=false"));
        assertThrows(IllegalStateException.class, () -> InitialAdminProvisioner.offlineArguments(
                "jdbc:postgresql://127.0.0.1:5432/paymesh_db"));
    }

    private SpringApplication application() {
        SpringApplication application = InitialAdminProvisioner.offlineApplication(StartupProbe.class);
        application.setRegisterShutdownHook(false);
        return application;
    }

    private void assertNonWeb(ConfigurableApplicationContext context) {
        assertInstanceOf(AnnotationConfigApplicationContext.class, context);
        assertFalse(context instanceof WebServerApplicationContext);
        assertTrue(context.getBeansOfType(WebServer.class).isEmpty());
        verify(context.getBean(ServletWebServerFactory.class), never())
                .getWebServer(any(ServletContextInitializer[].class));
        assertEquals(0, context.getBeanNamesForType(InitialAdminBootstrap.class).length);
        // The existing global guard still verifies the script's isolated database.
        assertEquals("true", context.getEnvironment().getProperty("paymesh.test.isolation-verified"));
    }

    private void assertSafetyProperties(ConfigurableApplicationContext context) {
        var environment = context.getEnvironment();
        assertEquals("none", environment.getProperty("spring.main.web-application-type"));
        assertEquals("false", environment.getProperty("spring.flyway.enabled"));
        assertEquals("validate", environment.getProperty("spring.jpa.hibernate.ddl-auto"));
        assertEquals("false", environment.getProperty("paymesh.settlement.scheduling-enabled"));
    }

    private String[] offlineArguments() {
        // This server-context probe uses the isolated test URL from the runner.
        // The actual provisioning args are separately asserted to pin paymesh_demo.
        return new String[]{"--spring.main.web-application-type=none", "--spring.flyway.enabled=false",
                "--spring.jpa.hibernate.ddl-auto=validate", "--paymesh.settlement.scheduling-enabled=false"};
    }
}
