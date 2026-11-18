package com.paymesh.backend.security.accounts;

import com.paymesh.backend.gateway.DemoGatewayTimeoutSimulator;
import java.util.Objects;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.env.Environment;

/** Fail-closed activation for the single local paymesh_demo fault scenario. */
@Configuration(proxyBeanMethods = false)
@Profile("demo")
@ConditionalOnProperty(name = "paymesh.demo.gateway-timeout.enabled", havingValue = "true")
class DemoGatewayFaultSimulationConfiguration {
    @Bean
    DemoGatewayTimeoutSimulator demoGatewayTimeoutSimulator() {
        return new DemoGatewayTimeoutSimulator();
    }

    /** Validate all migration target configuration before Flyway can write. */
    @Bean
    static BeanFactoryPostProcessor validateDemoFaultSimulationTarget(Environment environment) {
        return beanFactory -> {
            DemoDatabaseGuard.validateConfiguredUrl(environment.getProperty("spring.datasource.url"));
            if (environment.getProperty("spring.datasource.jndi-name") != null
                    || environment.getProperty("spring.flyway.url") != null
                    || !environment.getProperty("spring.flyway.enabled", Boolean.class, true)) {
                throw new IllegalStateException("Demo gateway fault simulation requires the guarded datasource and enabled Flyway migrations");
            }
            if (Boolean.parseBoolean(environment.getProperty("paymesh.settlement.scheduling-enabled", "false"))) {
                throw new IllegalStateException("Settlement scheduling must be disabled for deterministic demo fault simulation");
            }
        };
    }

    /** Verify the actual connected datasource immediately before Flyway migrates. */
    @Bean
    FlywayMigrationStrategy verifyDemoDatabaseBeforeMigration(DataSource dataSource, Environment environment) {
        String configuredUrl = Objects.requireNonNull(environment.getProperty("spring.datasource.url"));
        return (Flyway flyway) -> {
            DemoDatabaseGuard.verifyConnectedDatabase(dataSource, configuredUrl);
            flyway.migrate();
        };
    }
}
