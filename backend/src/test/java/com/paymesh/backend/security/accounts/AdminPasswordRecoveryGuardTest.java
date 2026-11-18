package com.paymesh.backend.security.accounts;
import java.util.*;
import java.sql.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
class AdminPasswordRecoveryGuardTest {
 @Test void requiresExactModeTargetAndUser() {
  assertDoesNotThrow(()->AdminRecoveryDatabaseGuard.configuration("RESET_EXISTING_ADMIN",AdminRecoveryDatabaseGuard.TARGET,"paymesh_demo_user",Map.of(),new Properties()));
  for(String target:List.of("jdbc:postgresql://127.0.0.1:5432/paymesh_db","jdbc:postgresql://localhost:5432/paymesh_demo","jdbc:postgresql://127.0.0.1:15432/paymesh_demo",AdminRecoveryDatabaseGuard.TARGET+"?currentSchema=x"))
   assertThrows(IllegalStateException.class,()->AdminRecoveryDatabaseGuard.configuration("RESET_EXISTING_ADMIN",target,"paymesh_demo_user",Map.of(),new Properties()));
  assertThrows(IllegalStateException.class,()->AdminRecoveryDatabaseGuard.configuration(null,AdminRecoveryDatabaseGuard.TARGET,"paymesh_demo_user",Map.of(),new Properties()));
  assertThrows(IllegalStateException.class,()->AdminRecoveryDatabaseGuard.configuration("RESET_EXISTING_ADMIN",AdminRecoveryDatabaseGuard.TARGET,"postgres",Map.of(),new Properties()));
  for(String override:List.of("SPRING_APPLICATION_JSON","LOGGING_LEVEL_ROOT","SPRING_JPA_SHOW_SQL"))
   assertThrows(IllegalStateException.class,()->AdminRecoveryDatabaseGuard.configuration("RESET_EXISTING_ADMIN",AdminRecoveryDatabaseGuard.TARGET,"paymesh_demo_user",Map.of(override,"unsafe"),new Properties()));
 }
 @Test void requiresConfirmationAndNeverAcceptsPasswordArguments() {
  assertTrue(AdminPasswordRecovery.confirmed("RESET ADMIN PASSWORD IN paymesh_demo"));
  for(String value:List.of("","yes","RESET ADMIN PASSWORD IN paymesh_db")) assertFalse(AdminPasswordRecovery.confirmed(value));
  var error=assertThrows(IllegalArgumentException.class,()->AdminPasswordRecovery.main(new String[]{"do-not-echo-this-secret"}));
  assertFalse(error.getMessage().contains("do-not-echo-this-secret"));
 }
 @Test void verifiesActualDatabaseAndNetworkIdentity() throws Exception {
  var source=mock(DriverManagerDataSource.class);var connection=mock(Connection.class);var metadata=mock(DatabaseMetaData.class);
  var statement=mock(Statement.class);var db=mock(ResultSet.class);var identity=mock(ResultSet.class);
  when(source.getConnection()).thenReturn(connection);when(connection.getMetaData()).thenReturn(metadata);
  when(metadata.getURL()).thenReturn(AdminRecoveryDatabaseGuard.TARGET);when(metadata.getUserName()).thenReturn("paymesh_demo_user");
  when(connection.createStatement()).thenReturn(statement);when(statement.executeQuery("SELECT current_database()")).thenReturn(db);
  when(db.next()).thenReturn(true);when(db.getString(1)).thenReturn("paymesh_demo");
  when(statement.executeQuery("SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()")).thenReturn(identity);
  when(identity.next()).thenReturn(true);when(identity.getString(1)).thenReturn("paymesh_demo");when(identity.getString(2)).thenReturn("paymesh_demo_user");when(identity.getString(3)).thenReturn("127.0.0.1");when(identity.getInt(4)).thenReturn(5432);
  assertDoesNotThrow(()->new AdminRecoveryDatabaseGuard().verify(source));
  when(identity.getInt(4)).thenReturn(15432);assertThrows(IllegalStateException.class,()->new AdminRecoveryDatabaseGuard().verify(source));
  when(db.getString(1)).thenReturn("paymesh_db");assertThrows(IllegalStateException.class,()->new AdminRecoveryDatabaseGuard().verify(source));
  when(db.getString(1)).thenReturn("paymesh_demo");when(metadata.getUserName()).thenReturn("postgres");assertThrows(IllegalStateException.class,()->new AdminRecoveryDatabaseGuard().verify(source));
 }
 @Test void recoveryConfigurationIsNotComponentScanned() {
  assertNull(AdminPasswordRecovery.RecoveryConfiguration.class.getAnnotation(org.springframework.context.annotation.Configuration.class));
  assertNull(AdminPasswordRecoveryTransaction.class.getAnnotation(org.springframework.stereotype.Service.class));
 }
 @Test void safeDiagnosticsDistinguishEveryRecoveryStageWithoutEchoingFailureDetails() {
  var secret=new IllegalArgumentException("private-password-and-bcrypt-hash-and-database-credentials");
  var messages=new HashSet<String>();
  for(var stage:AdminPasswordRecovery.Stage.values()) {
   String message=AdminPasswordRecovery.failureMessage(stage,secret);
   assertFalse(message.contains(secret.getMessage()));assertTrue(messages.add(message));
  }
  assertTrue(AdminPasswordRecovery.failureMessage(AdminPasswordRecovery.Stage.DATABASE,secret).startsWith("Database connection"));
  assertTrue(AdminPasswordRecovery.failureMessage(AdminPasswordRecovery.Stage.PASSWORD,secret).startsWith("Password validation"));
  assertTrue(AdminPasswordRecovery.failureMessage(AdminPasswordRecovery.Stage.CONTEXT,secret).startsWith("Offline Spring context"));
  assertTrue(AdminPasswordRecovery.failureMessage(AdminPasswordRecovery.Stage.RESET,secret).contains("commit could not be confirmed"));
 }
 @Test void repeatedDatabaseVerificationFailureIsClassifiedAsDatabaseEvenDuringReset() {
  assertEquals(AdminPasswordRecovery.failureMessage(AdminPasswordRecovery.Stage.DATABASE,new IllegalStateException()),
    AdminPasswordRecovery.failureMessage(AdminPasswordRecovery.Stage.RESET,new AdminRecoveryDatabaseGuard.VerificationFailure()));
 }

}
