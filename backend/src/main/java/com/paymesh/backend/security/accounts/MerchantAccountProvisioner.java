package com.paymesh.backend.security.accounts;

import com.paymesh.backend.PaymeshBackendApplication;
import com.paymesh.backend.security.accounts.AccountCredentials.AuthenticatedAccount;
import java.io.Console;
import java.util.Arrays;
import javax.sql.DataSource;

/** Explicit offline console command; this class is never an application runner or HTTP handler. */
public final class MerchantAccountProvisioner {
    private static final String CONFIRMATION = "PROVISION MERCHANT";

    private MerchantAccountProvisioner() {}

    public static void main(String[] args) {
        if (args.length != 0) {
            throw new IllegalArgumentException("This command accepts no arguments; use the interactive console");
        }
        Console console = System.console();
        if (console == null) {
            throw new IllegalStateException("A secure interactive console is required; passwords are not accepted from arguments or stdin");
        }

        String url = InitialAdminProvisioner.validatedTarget(
                System.getenv("PAYMESH_DEMO_DB_URL"), System.getenv(), System.getProperties());
        String databaseUser = System.getenv("PAYMESH_DB_USER");
        if (!"paymesh_demo_user".equals(databaseUser)) {
            throw new IllegalStateException("PAYMESH_DB_USER must be paymesh_demo_user for offline merchant provisioning");
        }
        String databasePassword = System.getenv("PAYMESH_DB_PASSWORD");
        if (databasePassword == null || databasePassword.isBlank()) {
            throw new IllegalStateException("PAYMESH_DB_PASSWORD must be configured in the environment");
        }

        String adminLogin = console.readLine("Existing ADMIN login: ");
        char[] adminPassword = console.readPassword("ADMIN password: ");
        String merchantId = console.readLine("Merchant identifier: ");
        String reviewReference = console.readLine("External ownership-review reference: ");
        String merchantLogin = console.readLine("New MERCHANT login: ");
        char[] merchantPassword = console.readPassword("New MERCHANT password (12+ characters): ");
        char[] confirmation = null;
        try {
            confirmation = console.readPassword("Confirm MERCHANT password: ");
            if (adminPassword == null || merchantPassword == null || confirmation == null
                    || !Arrays.equals(merchantPassword, confirmation)) {
                throw new IllegalArgumentException("Password confirmation failed");
            }
            console.printf("This will register and verify merchant '%s', create '%s', and grant its membership.%n",
                    merchantId, merchantLogin);
            if (!CONFIRMATION.equals(console.readLine("Type PROVISION MERCHANT to continue: "))) return;

            try (var context = InitialAdminProvisioner.offlineApplication(PaymeshBackendApplication.class)
                    .run(InitialAdminProvisioner.offlineArguments(url))) {
                // Verify the actual connection before credential verification (which can audit a denial)
                // and before any provisioning write.
                DemoDatabaseGuard.verifyOfflineProvisionerDatabase(context.getBean(DataSource.class), url);
                AccountCredentials credentials = context.getBean(AccountCredentials.class);
                AuthenticatedAccount actor = credentials.authenticate(adminLogin, adminPassword);
                AccountView account = context.getBean(AccountAdministration.class).provisionMerchant(
                        actor, merchantId, reviewReference, merchantLogin, merchantPassword);
                console.printf("Merchant provisioned atomically. MERCHANT login: %s; account id: %s%n",
                        account.login(), account.userId());
            } catch (RuntimeException ex) {
                console.printf("Provisioning failed. The account, merchant, verification, membership, and success audits use one transaction. "
                        + "If the database connection failed during commit, inspect state through an authorized administrative process before retrying; "
                        + "duplicate merchants and logins are refused and never overwritten.%n");
                throw ex;
            }
        } finally {
            if (adminPassword != null) Arrays.fill(adminPassword, '\0');
            if (merchantPassword != null) Arrays.fill(merchantPassword, '\0');
            if (confirmation != null) Arrays.fill(confirmation, '\0');
        }
    }
}
