package com.paymesh.backend.security.auth;

import jakarta.servlet.DispatcherType;
import java.util.ArrayList;
import java.util.List;
import org.springframework.http.HttpMethod;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.*;

/** Public health and independently authenticated provider/settlement endpoints only. */
final class LegacyEndpointCatalog {
    private LegacyEndpointCatalog() {}
    static RequestMatcher matcher() {
        List<RequestMatcher> routes = new ArrayList<>();
        add(routes,HttpMethod.GET,"/api/v1/checkout/{token}");add(routes,HttpMethod.GET,"/api/v1/checkout/{token}/status");add(routes,HttpMethod.POST,"/api/v1/checkout/{token}/pay");
        get(routes, "/api/v1/payments/health");
        post(routes, "/api/v1/webhooks/mock-razorpay");
        post(routes, "/api/v1/webhooks/mock-stripe");
        post(routes, "/api/v1/settlement/payments/{paymentId}/reconcile");
        get(routes, "/api/v1/settlement/payments/{paymentId}/reconciliation");
        get(routes, "/api/v1/settlement/payments/{paymentId}/webhooks");
        post(routes, "/api/v1/settlement/webhooks/{id}/retry");
        get(routes, "/actuator/health");
        get(routes, "/actuator/health/liveness");
        get(routes, "/actuator/health/readiness");
        // Internal error dispatch only, not a direct public /error request.
        routes.add(new AndRequestMatcher(new DispatcherTypeRequestMatcher(DispatcherType.ERROR),
                PathPatternRequestMatcher.withDefaults().matcher("/error")));
        return new OrRequestMatcher(routes);
    }
    private static void get(List<RequestMatcher> routes, String path) {
        add(routes, HttpMethod.GET, path); add(routes, HttpMethod.HEAD, path); add(routes, HttpMethod.OPTIONS, path);
    }
    private static void post(List<RequestMatcher> routes, String path) {
        add(routes, HttpMethod.POST, path); add(routes, HttpMethod.OPTIONS, path);
    }
    private static void add(List<RequestMatcher> routes, HttpMethod method, String path) {
        routes.add(PathPatternRequestMatcher.withDefaults().matcher(method, path));
    }
}
