package com.paymesh.backend.security.auth;

import java.util.ArrayList;
import java.util.List;
import org.springframework.http.HttpMethod;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.*;

final class BusinessEndpointCatalog {
    private BusinessEndpointCatalog() {}
    static RequestMatcher payments() {
        List<RequestMatcher> paths = new ArrayList<>();
        add(paths,HttpMethod.POST,"/api/v1/payments/{paymentId}/ai/chat");
        add(paths, HttpMethod.POST, "/api/v1/payments");
        get(paths, "/api/v1/payments/{paymentId}");
        add(paths, HttpMethod.POST, "/api/v1/payments/{paymentId}/process");
        add(paths, HttpMethod.POST, "/api/v1/payments/{paymentId}/investigate");
        get(paths, "/api/v1/payments/{paymentId}/gateway-transactions");
        add(paths, HttpMethod.POST, "/api/v1/payments/{paymentId}/refund");
        get(paths, "/api/v1/payments/{paymentId}/refund");
        get(paths, "/api/v1/payments/{paymentId}/refunds");
        return new OrRequestMatcher(paths);
    }
    static RequestMatcher admin() {
        List<RequestMatcher> paths = new ArrayList<>();conversations(paths,"admin"); add(paths,HttpMethod.POST,"/api/v1/admin/ai/chat");add(paths, HttpMethod.POST, "/api/v1/admin/accounts"); get(paths, "/actuator"); get(paths, "/actuator/info");
        for(String path : List.of("/api/v1/admin/analytics","/api/v1/admin/dashboard","/api/v1/admin/merchants","/api/v1/admin/merchant","/api/v1/admin/payments","/api/v1/admin/refunds","/api/v1/admin/payments/{id}","/api/v1/admin/refunds/{id}","/api/v1/admin/audit","/api/v1/admin/accounts","/api/v1/admin/profile")) get(paths,path);
        for(String path : List.of("/api/v1/admin/merchant/approve","/api/v1/admin/merchant/reject","/api/v1/admin/merchant/suspend","/api/v1/admin/merchant/reactivate","/api/v1/admin/profile/password")) add(paths,HttpMethod.POST,path);
        return new OrRequestMatcher(paths);
    }
    static RequestMatcher merchant() {List<RequestMatcher> paths=new ArrayList<>();conversations(paths,"merchant");add(paths,HttpMethod.POST,"/api/v1/merchant/ai/chat");for(String p:List.of("analytics","dashboard","payments","refunds","profile"))get(paths,"/api/v1/merchant/"+p);add(paths,HttpMethod.POST,"/api/v1/merchant/profile/password");get(paths,"/api/v1/merchant/payment-links");get(paths,"/api/v1/merchant/payment-links/{id}");add(paths,HttpMethod.POST,"/api/v1/merchant/payment-links");add(paths,HttpMethod.POST,"/api/v1/merchant/payment-links/{id}/cancel");return new OrRequestMatcher(paths);}
    private static void conversations(List<RequestMatcher> paths,String portal){String b="/api/v1/"+portal+"/ai/conversations";for(String p:List.of(b,b+"/{id}",b+"/creations/{requestId}",b+"/{id}/messages",b+"/{id}/requests/{requestId}"))get(paths,p);for(String p:List.of(b,b+"/{id}/messages",b+"/{id}/rename",b+"/{id}/delete"))add(paths,HttpMethod.POST,p);}
    static RequestMatcher all() { return new OrRequestMatcher(payments(), admin(), merchant()); }
    private static void get(List<RequestMatcher> paths, String path) {
        add(paths, HttpMethod.GET, path); add(paths, HttpMethod.HEAD, path);
    }
    private static void add(List<RequestMatcher> paths, HttpMethod method, String path) {
        paths.add(PathPatternRequestMatcher.withDefaults().matcher(method, path));
        paths.add(PathPatternRequestMatcher.withDefaults().matcher(HttpMethod.OPTIONS, path));
    }
}
