package com.paymesh.backend.security;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import org.springframework.stereotype.Component;
import org.springframework.core.annotation.Order;
import org.springframework.core.Ordered;
import org.springframework.web.filter.OncePerRequestFilter;
/** Safe failures before MVC can echo a capability path in default error payloads. */
@Component @Order(Ordered.HIGHEST_PRECEDENCE+21)
public final class CheckoutHttpPolicyFilter extends OncePerRequestFilter {
 @Override protected boolean shouldNotFilter(HttpServletRequest r){return !r.getRequestURI().startsWith(r.getContextPath()+"/api/v1/checkout/");}
 @Override protected void doFilterInternal(HttpServletRequest r,HttpServletResponse s,FilterChain chain)throws IOException,ServletException{
  s.setHeader("Cache-Control","no-store");s.setHeader("Referrer-Policy","no-referrer");s.setHeader("X-Content-Type-Options","nosniff");
  if(r.getRequestURI().length()>256||r.getQueryString()!=null||r.getHeader("Transfer-Encoding")!=null||"GET".equals(r.getMethod())&&r.getContentLengthLong()>0){deny(s,400);return;}
  if("POST".equals(r.getMethod())&&(r.getContentType()==null||!r.getContentType().split(";",2)[0].equalsIgnoreCase("application/json"))){deny(s,415);return;}chain.doFilter(r,s);
 }
 private void deny(HttpServletResponse s,int status)throws IOException{s.setStatus(status);s.setContentType("application/json");s.getWriter().write("{\"message\":\"Invalid checkout request.\"}");}
}
