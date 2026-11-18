package com.paymesh.backend.security.auth;
import com.paymesh.backend.security.accounts.CheckoutDemoGate;
import java.time.*;
import javax.sql.DataSource;
import org.springframework.mock.env.MockEnvironment;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class CheckoutSafetyTest {
 @Test void controlsDisabledWithoutDatabaseAccess(){var source=mock(DataSource.class);assertFalse(new CheckoutDemoGate(new MockEnvironment(),source).enabled());verifyNoInteractions(source);}
 @Test void productionAndNonDemoDatabaseAreRejected(){var env=new MockEnvironment();env.setActiveProfiles("production");env.setProperty("paymesh.demo.checkout-controls.enabled","true");assertThrows(IllegalStateException.class,()->new CheckoutDemoGate(env,mock(DataSource.class)));env.setActiveProfiles("demo");env.setProperty("spring.datasource.url","jdbc:postgresql://127.0.0.1:5432/paymesh_isolated");assertThrows(IllegalStateException.class,()->CheckoutDemoGate.requireSafe(env));}
 @Test void publicRateLimitsAreBoundedAndTokenScoped(){var rate=new CheckoutRateLimit(Clock.fixed(Instant.EPOCH,ZoneOffset.UTC));for(int i=0;i<6;i++)assertTrue(rate.allow("local","token-a",true));assertFalse(rate.allow("local","token-a",true));assertTrue(rate.allow("local","token-b",true));for(int i=0;i<60;i++)assertTrue(rate.allow("local","token-a",false));assertFalse(rate.allow("local","token-a",false));}
 @Test void rateWindowResetsWithoutSleep(){final long[] millis={0};var clock=new Clock(){public ZoneId getZone(){return ZoneOffset.UTC;}public Clock withZone(ZoneId z){return this;}public Instant instant(){return Instant.ofEpochMilli(millis[0]);}};var rate=new CheckoutRateLimit(clock);for(int i=0;i<6;i++)assertTrue(rate.allow("x","y",true));assertFalse(rate.allow("x","y",true));millis[0]=60001;assertTrue(rate.allow("x","y",true));}
}
