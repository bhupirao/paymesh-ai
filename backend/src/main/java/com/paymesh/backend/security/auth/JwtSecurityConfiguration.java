package com.paymesh.backend.security.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paymesh.backend.security.SecurityStateUnavailableException;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.*;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.*;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class JwtSecurityConfiguration {
    @Bean @Order(1)
    SecurityFilterChain legacyCompatibility(HttpSecurity http, ObjectMapper json) throws Exception {
        SecurityResponses responses = new SecurityResponses(json);
        common(http, responses);
        // Only public health and delegated-auth routes match. This deliberately contains
        // no JWT filter, preserving webhook HMAC and opaque settlement bearer handling.
        http.securityMatcher(LegacyEndpointCatalog.matcher())
                .authorizeHttpRequests(rules -> rules.requestMatchers(LegacyEndpointCatalog.matcher()).permitAll()
                        .anyRequest().denyAll());
        return http.build();
    }

    @Bean @Order(2)
    SecurityFilterChain businessEndpoints(HttpSecurity http, JwtDecoder decoder, JwtAccountValidator validator,
                                         ObjectMapper json) throws Exception {
        SecurityResponses responses = new SecurityResponses(json);
        common(http, responses);
        http.securityMatcher(BusinessEndpointCatalog.all())
                .authorizeHttpRequests(rules -> rules.requestMatchers(BusinessEndpointCatalog.admin()).hasRole("ADMIN")
                        .requestMatchers(BusinessEndpointCatalog.merchant()).hasRole("MERCHANT")
                        .requestMatchers(BusinessEndpointCatalog.payments()).hasAnyRole("ADMIN", "MERCHANT")
                        .anyRequest().denyAll());
        bearer(http, decoder, validator, responses);
        return http.build();
    }

    @Bean @Order(3)
    SecurityFilterChain authenticationEndpoints(HttpSecurity http, JwtDecoder decoder, JwtAccountValidator validator,
                                                LoginRateLimiter limiter, ObjectMapper json) throws Exception {
        SecurityResponses responses = new SecurityResponses(json);
        common(http, responses);
        http.securityMatcher("/api/v1/auth/**")
                .authorizeHttpRequests(rules -> rules.requestMatchers(org.springframework.http.HttpMethod.POST,
                        "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh", "/api/v1/auth/logout", "/api/v1/auth/logout-all", "/api/v1/auth/password/forgot", "/api/v1/auth/password/verify-otp", "/api/v1/auth/password/reset").permitAll()
                        .requestMatchers(org.springframework.http.HttpMethod.GET,"/api/v1/auth/password/capabilities").permitAll().anyRequest().denyAll())
                .addFilterBefore(new LoginRateLimitFilter(limiter, responses), BearerTokenAuthenticationFilter.class)
                .oauth2ResourceServer(resource -> resource.authenticationEntryPoint((req, res, ex) -> responses.writeAuthenticationFailure(res, ex))
                        .jwt(jwt -> jwt.decoder(decoder).jwtAuthenticationConverter(token -> {
                            try {
                                var state = validator.current(token);
                                return new JwtAuthenticationToken(token, state.financialRoles().stream()
                                        .map(r -> new SimpleGrantedAuthority("ROLE_" + r.name())).toList(), state.userId().toString());
                            } catch (SecurityStateUnavailableException ex) { throw ex; }
                            catch (RuntimeException ex) {
                                throw new OAuth2AuthenticationException(new OAuth2Error("invalid_token"));
                            }
                        })));
        return http.build();
    }

    @Bean @Order(4)
    SecurityFilterChain denyUnmatched(HttpSecurity http, ObjectMapper json, JwtDecoder decoder, JwtAccountValidator validator) throws Exception {
        common(http, new SecurityResponses(json));
        http.authorizeHttpRequests(rules -> rules.anyRequest().denyAll());
        bearer(http, decoder, validator, new SecurityResponses(json));
        return http.build();
    }

    private void bearer(HttpSecurity http, JwtDecoder decoder, JwtAccountValidator validator, SecurityResponses responses) throws Exception {
        http.oauth2ResourceServer(resource -> resource.authenticationEntryPoint((req, res, ex) -> responses.writeAuthenticationFailure(res, ex))
                .jwt(jwt -> jwt.decoder(decoder).jwtAuthenticationConverter(token -> {
                    try {
                        var state = validator.current(token);
                        return new JwtAuthenticationToken(token, state.financialRoles().stream()
                                .map(r -> new SimpleGrantedAuthority("ROLE_" + r.name())).toList(), state.userId().toString());
                    } catch (SecurityStateUnavailableException ex) { throw ex; }
                    catch (RuntimeException ex) {
                        throw new OAuth2AuthenticationException(new OAuth2Error("invalid_token"));
                    }
                })));
    }

    private void common(HttpSecurity http, SecurityResponses responses) throws Exception {
        http.csrf(AbstractHttpConfigurer::disable).formLogin(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable).logout(AbstractHttpConfigurer::disable)
                .requestCache(AbstractHttpConfigurer::disable)
                .sessionManagement(sessions -> sessions.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .securityContext(context -> context.requireExplicitSave(true))
                .exceptionHandling(errors -> errors.authenticationEntryPoint((req, res, ex) -> responses.write(res, 401))
                        .accessDeniedHandler((req, res, ex) -> responses.write(res, 403)));
    }
}
