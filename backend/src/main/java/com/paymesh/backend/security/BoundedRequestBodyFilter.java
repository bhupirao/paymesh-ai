package com.paymesh.backend.security;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Bounds bytes actually consumed before JSON deserialization on credential and webhook routes. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 20)
public final class BoundedRequestBodyFilter extends OncePerRequestFilter {
    private static final Map<String, Integer> LIMITS = Map.ofEntries(
            Map.entry("/api/v1/merchant/payment-links",4096),Map.entry("/api/v1/admin/profile/password",4096),Map.entry("/api/v1/merchant/profile/password",4096),Map.entry("/api/v1/admin/merchant/approve",4096),Map.entry("/api/v1/admin/merchant/reject",4096),Map.entry("/api/v1/admin/merchant/suspend",4096),Map.entry("/api/v1/admin/merchant/reactivate",4096),Map.entry("/api/v1/admin/accounts",4096),Map.entry("/api/v1/auth/login",4096),Map.entry("/api/v1/auth/register",16384),
            Map.entry("/api/v1/auth/refresh",4096),Map.entry("/api/v1/auth/logout",4096),Map.entry("/api/v1/auth/logout-all",4096),
            Map.entry("/api/v1/auth/password/forgot",4096),Map.entry("/api/v1/auth/password/verify-otp",4096),Map.entry("/api/v1/auth/password/reset",4096),
            Map.entry("/api/v1/webhooks/mock-razorpay",65536),Map.entry("/api/v1/webhooks/mock-stripe",65536));

    @Override protected boolean shouldNotFilter(HttpServletRequest request) {
        return !"POST".equals(request.getMethod()) || !(conversation(path(request))||chat(path(request))||LIMITS.containsKey(path(request)) || (path(request).matches("/api/v1/merchant/payment-links/[^/]+/cancel")||path(request).matches("/api/v1/checkout/[^/]+/pay")));
    }

    @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        if (path(request).startsWith("/api/v1/admin/")||path(request).startsWith("/api/v1/merchant/")) response.setHeader("Cache-Control", "no-store");
        int limit = conversation(path(request))?8192:chat(path(request))?32768:LIMITS.getOrDefault(path(request),4096);
        if (request.getContentLengthLong() > limit) { tooLarge(response); return; }
        byte[] body = readBounded(request.getInputStream(), limit);
        if (body == null) { tooLarge(response); return; }
        chain.doFilter(new CachedBodyRequest(request, body), response);
    }

    private boolean conversation(String path){return path.matches("/api/v1/(merchant|admin)/ai/conversations(?:/[^/]+/(?:messages|rename|delete))?");}
    private boolean chat(String path){return path.equals("/api/v1/merchant/ai/chat")||path.equals("/api/v1/admin/ai/chat")||path.matches("/api/v1/payments/[^/]+/ai/chat");}
    static byte[] readBounded(InputStream input, int limit) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream(Math.min(limit, 4096));
        byte[] buffer = new byte[4096];
        int total = 0, count;
        while ((count = input.read(buffer, 0, Math.min(buffer.length, limit + 1 - total))) != -1) {
            total += count;
            if (total > limit) return null;
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    private static String path(HttpServletRequest request) {
        String uri = request.getRequestURI(), context = request.getContextPath();
        return context == null || context.isEmpty() ? uri : uri.substring(context.length());
    }

    private static void tooLarge(HttpServletResponse response) throws IOException {
        response.setHeader("Cache-Control", "no-store");
        response.setStatus(HttpServletResponse.SC_REQUEST_ENTITY_TOO_LARGE);
        response.setContentType("application/json");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write("{\"status\":413,\"message\":\"Request body too large\"}");
    }

    private static final class CachedBodyRequest extends HttpServletRequestWrapper {
        private final byte[] body;
        CachedBodyRequest(HttpServletRequest request, byte[] body) { super(request); this.body = body; }
        @Override public int getContentLength() { return body.length; }
        @Override public long getContentLengthLong() { return body.length; }
        @Override public ServletInputStream getInputStream() {
            ByteArrayInputStream input = new ByteArrayInputStream(body);
            return new ServletInputStream() {
                @Override public int read() { return input.read(); }
                @Override public boolean isFinished() { return input.available() == 0; }
                @Override public boolean isReady() { return true; }
                @Override public void setReadListener(ReadListener listener) {
                    Objects.requireNonNull(listener);
                    try { if (isFinished()) listener.onAllDataRead(); else listener.onDataAvailable(); }
                    catch (IOException ex) { listener.onError(ex); }
                }
            };
        }
        @Override public BufferedReader getReader() { return new BufferedReader(new InputStreamReader(getInputStream(), getCharacterEncoding() == null ? StandardCharsets.UTF_8 : java.nio.charset.Charset.forName(getCharacterEncoding()))); }
    }
}
