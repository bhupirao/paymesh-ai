package com.paymesh.backend.security;

import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

/** Keeps unrestricted financial capabilities and repositories out of HTTP/application entry points. */
class InternalFinancialBoundaryArchitectureTest {
    private static final Path MAIN = Path.of("src/main/java/com/paymesh/backend");
    private static final Set<String> TRUSTED_INTERNAL_CONSUMERS = Set.of(
            // Reviewed Phase683 capability boundary: token-derived immutable link claim,
            // then package-private post-claim execution. Never injected into HTTP controllers.
            "security/accounts/CheckoutTransactions.java",
            "service/impl/AcceptedPaymentExecution.java",
            "service/impl/PaymentServiceImpl.java",
            "service/impl/RefundServiceImpl.java",
            "service/impl/GatewayTransactionServiceImpl.java",
            "service/impl/FinancialPaymentOperations.java",
            "service/impl/FinancialRefundOperations.java",
            "service/impl/FinancialGatewayTransactionOperations.java",
            "service/impl/PaymentOrchestrationServiceImpl.java",
            "security/business/BusinessProcessingClaims.java");
    private static final Set<String> TRUSTED_REPOSITORY_CONSUMERS = Set.of(
            "security/business/BusinessAccess.java",
            "security/business/BusinessProcessingClaims.java",
            "service/impl/FinancialPaymentOperations.java",
            "service/impl/FinancialRefundOperations.java",
            "service/impl/FinancialGatewayTransactionOperations.java",
            "service/impl/GatewayTransactionServiceImpl.java",
            "settlement/WebhookProcessor.java",
            "settlement/OutcomeApplier.java",
            "settlement/ReconciliationService.java",
            "settlement/SettlementAdminController.java");

    @Test
    void internalCapabilitiesDoNotInheritPublicBusinessServiceContracts() throws IOException {
        for (String name : List.of("InternalPaymentService.java", "InternalRefundService.java", "InternalGatewayTransactionService.java")) {
            String source = Files.readString(MAIN.resolve("service/internal").resolve(name));
            assertFalse(source.contains("extends "), name + " must declare a narrow internal contract");
            assertFalse(source.contains("implements "), name + " must not inherit a public service surface");
        }
    }

    @Test
    void onlyReviewedComponentsMayInjectInternalFinancialCapabilities() throws IOException {
        assertNoUnapprovedInjection("InternalPaymentService", TRUSTED_INTERNAL_CONSUMERS);
        assertNoUnapprovedInjection("InternalRefundService", TRUSTED_INTERNAL_CONSUMERS);
        assertNoUnapprovedInjection("InternalGatewayTransactionService", TRUSTED_INTERNAL_CONSUMERS);
        assertNoUnapprovedInjection("FinancialPaymentOperations", TRUSTED_INTERNAL_CONSUMERS);
        assertNoUnapprovedInjection("FinancialRefundOperations", TRUSTED_INTERNAL_CONSUMERS);
        assertNoUnapprovedInjection("FinancialGatewayTransactionOperations", TRUSTED_INTERNAL_CONSUMERS);
    }

    @Test
    void controllersCannotInjectInternalServicesOrFinancialRepositories() throws IOException {
        try (Stream<Path> files = Files.walk(MAIN.resolve("controller"))) {
            for (Path file : files.filter(p -> p.toString().endsWith(".java")).toList()) {
                String source = Files.readString(file);
                assertFalse(source.contains("service.internal"), file.toString());
                assertFalse(source.contains("Repository"), file.toString());
            }
        }
    }

    @Test
    void financialRepositoriesAreLimitedToScopedFacadesAndTrustedWorkers() throws IOException {
        Set<String> repositories = Set.of("PaymentRepository", "RefundRepository", "GatewayTransactionRepository");
        try (Stream<Path> files = Files.walk(MAIN)) {
            for (Path file : files.filter(p -> p.toString().endsWith(".java")
                    && !p.startsWith(MAIN.resolve("repository"))).toList()) {
                String source = Files.readString(file);
                if (repositories.stream().noneMatch(source::contains)) continue;
                String relative = MAIN.relativize(file).toString().replace('\\', '/');
                assertTrue(TRUSTED_REPOSITORY_CONSUMERS.contains(relative),
                        () -> "Unreviewed financial repository consumer: " + relative);
            }
        }
    }

    @Test
    void checkoutContinuationCannotBeInvokedAsAPublicPaymentApi() throws Exception {
        var method=com.paymesh.backend.service.impl.AcceptedPaymentExecution.class.getDeclaredMethod("execute",com.paymesh.backend.dto.PaymentResponse.class,String.class);
        assertFalse(java.lang.reflect.Modifier.isPublic(method.getModifiers()));
        String controller=Files.readString(MAIN.resolve("security/auth/CheckoutController.java"));
        assertFalse(controller.contains("service.internal"));assertFalse(controller.contains("Repository"));assertFalse(controller.contains("PaymentResponse"));
        String coordinator=Files.readString(MAIN.resolve("service/impl/CheckoutExecution.java"));
        assertFalse(coordinator.contains("@RestController"));assertTrue(coordinator.indexOf("transactions.accept(")<coordinator.indexOf("orchestration.execute("));
    }

    private void assertNoUnapprovedInjection(String capability, Set<String> approved) throws IOException {
        try (Stream<Path> files = Files.walk(MAIN)) {
            for (Path file : files.filter(p -> p.toString().endsWith(".java")
                    && !p.startsWith(MAIN.resolve("service/internal"))).toList()) {
                String source = Files.readString(file);
                if (!source.contains(capability)) continue;
                String relative = MAIN.relativize(file).toString().replace('\\', '/');
                assertTrue(approved.contains(relative),
                        () -> "Unreviewed internal financial capability consumer: " + relative);
            }
        }
    }
}
