package com.paymesh.backend.security.accounts;

import java.util.Set;
import java.util.UUID;

public record AccountView(UUID userId, String login, boolean enabled, long authorizationVersion, Set<AccountRole> roles) {}
