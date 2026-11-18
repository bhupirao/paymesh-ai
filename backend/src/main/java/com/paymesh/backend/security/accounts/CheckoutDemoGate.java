package com.paymesh.backend.security.accounts;
import java.util.*;
import javax.sql.DataSource;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;
import org.springframework.context.ApplicationListener;
import org.springframework.boot.web.context.WebServerInitializedEvent;
import org.springframework.boot.web.embedded.tomcat.TomcatWebServer;
/** Separate from OTP. Disabled by default; a flag alone cannot enable outcome controls. */
@Component
public class CheckoutDemoGate implements ApplicationListener<WebServerInitializedEvent> {
 private final boolean configured;private volatile boolean bound;
 public CheckoutDemoGate(Environment env,DataSource source){configured=env.getProperty("paymesh.demo.checkout-controls.enabled",Boolean.class,false);if(!configured)return;requireSafe(env);DemoDatabaseGuard.verifyConnectedDatabase(source,AdminRecoveryDatabaseGuard.TARGET);
  try(var c=source.getConnection();var s=c.createStatement();var r=s.executeQuery(AdminRecoveryDatabaseGuard.IDENTITY_QUERY)){if(!r.next()||!"paymesh_demo".equals(r.getString(1))||!"paymesh_demo_user".equals(r.getString(2))||!"127.0.0.1".equals(r.getString(3))||r.getInt(4)!=5432)throw new IllegalStateException("Unsafe checkout demo target");}catch(java.sql.SQLException ex){throw new IllegalStateException("Checkout demo target unavailable");}}
 public static void requireSafe(Environment env){if(!Set.of(env.getActiveProfiles()).equals(Set.of("demo"))||!"127.0.0.1".equals(env.getProperty("server.address"))||!"18080".equals(env.getProperty("server.port"))||!AdminRecoveryDatabaseGuard.TARGET.equals(env.getProperty("spring.datasource.url"))||!"paymesh_demo_user".equals(env.getProperty("spring.datasource.username"))||!"http://127.0.0.1:5500".equals(env.getProperty("paymesh.sessions.origin"))||!env.getProperty("paymesh.sessions.local-http",Boolean.class,false)||!"none".equals(env.getProperty("server.forward-headers-strategy","none"))||env.getProperty("server.ssl.enabled",Boolean.class,false)||!"NO_PUBLIC_PROXY_OR_TUNNEL".equals(env.getProperty("paymesh.demo.checkout-controls.operator-confirmation")))throw new IllegalStateException("Checkout controls require the private loopback demo");}
 @Override public void onApplicationEvent(WebServerInitializedEvent e){if(!configured)return;if(!(e.getWebServer() instanceof TomcatWebServer server))throw new IllegalStateException("Unsupported demo connector");for(var c:server.getTomcat().getService().findConnectors()){Object a=c.getProperty("address");String host=a instanceof java.net.InetAddress n?n.getHostAddress():String.valueOf(a);if(!"127.0.0.1".equals(host)||c.getPort()!=18080)throw new IllegalStateException("Unsafe demo connector");}bound=true;}
 public boolean enabled(){return configured&&bound;}
}
