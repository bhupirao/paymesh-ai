package com.paymesh.backend.security.accounts;

import jakarta.persistence.*;

@Entity(name = "SecurityRole")
@Table(name = "roles")
public class Role {
    @Id @Column(name = "role_name", length = 20) private String roleName;
    protected Role() {}
    public String getRoleName() { return roleName; }
}
