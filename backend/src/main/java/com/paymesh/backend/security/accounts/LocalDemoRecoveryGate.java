package com.paymesh.backend.security.accounts;

import java.util.*;
import javax.sql.DataSource;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import org.springframework.context.ApplicationListener;
import org.springframework.boot.web.context.WebServerInitializedEvent;
import org.springframework.boot.web.embedded.tomcat.TomcatWebServer;

/** This insecure ownership demonstration can never be enabled by a flag alone. */
@Component
public class LocalDemoRecoveryGate implements ApplicationListener<WebServerInitializedEvent> {
    private final boolean configured;private final String key;private volatile boolean bound;
    public LocalDemoRecoveryGate(Environment env,DataSource source) {
        configured=env.getProperty("paymesh.demo.password-recovery.enabled",Boolean.class,false);
        key=env.getProperty("paymesh.demo.password-recovery.key","");if(!configured)return;
        requireSafeConfiguration(env);
        if(key.length()<64)throw new IllegalStateException("Local demo recovery requires a private high-entropy digest key");
        DemoDatabaseGuard.verifyConnectedDatabase(source,AdminRecoveryDatabaseGuard.TARGET);
        try(var c=source.getConnection();var s=c.createStatement();var row=s.executeQuery(AdminRecoveryDatabaseGuard.IDENTITY_QUERY)) {
            if(!row.next()||!"paymesh_demo".equals(row.getString(1))||!"paymesh_demo_user".equals(row.getString(2))||!"127.0.0.1".equals(row.getString(3))||row.getInt(4)!=5432)throw new IllegalStateException("Unsafe demo recovery database");
        }catch(java.sql.SQLException ex){throw new IllegalStateException("Demo recovery target unavailable");}
    }
    public static void requireSafeConfiguration(Environment env) {
        if(!Set.of(env.getActiveProfiles()).equals(Set.of("demo"))||!"127.0.0.1".equals(env.getProperty("server.address"))||!"18080".equals(env.getProperty("server.port"))
           ||!AdminRecoveryDatabaseGuard.TARGET.equals(env.getProperty("spring.datasource.url"))||!"paymesh_demo_user".equals(env.getProperty("spring.datasource.username"))
           ||!"http://127.0.0.1:5500".equals(env.getProperty("paymesh.sessions.origin"))||!env.getProperty("paymesh.sessions.local-http",Boolean.class,false)
           ||!"NO_PUBLIC_PROXY_OR_TUNNEL".equals(env.getProperty("paymesh.demo.password-recovery.operator-confirmation"))||!"none".equals(env.getProperty("server.forward-headers-strategy","none"))||env.getProperty("server.ssl.enabled",Boolean.class,false))throw new IllegalStateException("Local recovery is restricted to the reviewed loopback demo deployment");
    }
    @Override public void onApplicationEvent(WebServerInitializedEvent event) {
        if(!configured)return;
        if(!(event.getWebServer() instanceof TomcatWebServer server))throw new IllegalStateException("Unsupported local recovery server");
        for(var connector:server.getTomcat().getService().findConnectors()) {
            Object address=connector.getProperty("address");
            String host=address instanceof java.net.InetAddress a?a.getHostAddress():String.valueOf(address);
            if(!"127.0.0.1".equals(host)||connector.getPort()!=18080)throw new IllegalStateException("Public connector denies local recovery");
        }
        bound=true;
    }
    @org.springframework.context.annotation.Bean
    static org.springframework.beans.factory.config.BeanFactoryPostProcessor validateBeforeStartup(Environment env) {
        return factory->{if(env.getProperty("paymesh.demo.password-recovery.enabled",Boolean.class,false))requireSafeConfiguration(env);};
    }
    public boolean enabled(){return configured&&bound;}
    public String key(){if(!enabled())throw new IllegalStateException("Local recovery is disabled");return key;}
}
