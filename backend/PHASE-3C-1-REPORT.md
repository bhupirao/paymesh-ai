# Phase 3C.1 report: trusted financial worker boundaries

## Result

Completed Phase 3C Step 1. The internal payment, refund and gateway transaction
interfaces no longer inherit their public business service interfaces. Each
declares only its own operations. This narrows accidental coupling while retaining
the methods required by secured facades, payment orchestration and trusted workers.

## Architecture-test findings and allowlist decisions

The first verification run found the two reported allowlist omissions:

- `FinancialPaymentOperations` was not listed as an approved `InternalPaymentService`
  consumer. It implements the trusted payment core and is injected by the secured
  `PaymentServiceImpl` facade and payment orchestration for financial processing.
- `GatewayTransactionServiceImpl` was not listed as an approved financial
  repository consumer. It obtains the actor through `BusinessAccess`, authorizes
  the payment before initiating/completing/marking transactions, and queries a
  transaction only through `findAccessibleById` with caller, version and server
  role scope before delegating to the internal core.

Those dependencies are legitimate and do not introduce a bypass or cross-merchant
exposure. The architecture test then exposed the same precise omission for
`FinancialRefundOperations` and `FinancialGatewayTransactionOperations`; both are
the respective trusted financial core implementations. They were added as exact
class entries after checking their role as internal service implementations.

Only these three exact class names were added to existing allowlists. No package
allowlist was added, no assertion was weakened, and no failing test was removed.

## Modified files

- `src/test/java/com/paymesh/backend/security/InternalFinancialBoundaryArchitectureTest.java`
  — Added exact reviewed consumers for the trusted financial implementations and
  secured gateway facade.
- `src/main/java/com/paymesh/backend/service/internal/InternalPaymentService.java`
  — Replaced public-interface inheritance with a directly declared narrow contract.
- `src/main/java/com/paymesh/backend/service/internal/InternalRefundService.java`
  — Replaced public-interface inheritance with a directly declared narrow contract.
- `src/main/java/com/paymesh/backend/service/internal/InternalGatewayTransactionService.java`
  — Replaced public-interface inheritance with a directly declared narrow contract.
- `PHASE-3C-1-REPORT.md` — This report.

No production financial algorithms, secured facade checks, webhook workers,
reconciliation behavior, migrations, or database records were changed.

## Architecture test coverage

`InternalFinancialBoundaryArchitectureTest` checks that:

1. Internal capability interfaces do not extend/implement public service contracts.
2. Only exact reviewed classes may reference internal financial capabilities.
3. HTTP controllers cannot inject internal services or repositories.
4. Financial repositories are limited to exact scoped facades and trusted workers.

## Verification

The first full isolated run completed with two failures from missing exact allowlist
entries. After those were added, the next run exposed the two corresponding core
implementation classes; their exact entries were added without broadening the
allowlist. A subsequent attempt to rerun after an interrupted test process could
not bind the script's isolated port because that earlier run's server was still
active. The process was checked by its port and data directory; the original
isolated run then completed successfully and shut PostgreSQL down before another
test launch.

Final full regression run: `bash scripts/test-isolated.sh` — **160 tests, 0
failures, 0 errors, 0 skipped; BUILD SUCCESS.** This includes all four new
architecture tests passing.

Isolated PostgreSQL shutdown was confirmed: the guarded script reported
`server stopped` after the successful run. Its retained data directory was
`/private/tmp/paymesh-webhook-test.QrdGfz/data`, and its temporary cluster was
created for the verified isolated test database. The application database was
not used or modified.

## Remaining security concerns

Internal financial services and their implementations remain callable by other
code within the Spring application. The exact-class architecture test guards
current source references, but Java/Spring visibility is not a hard runtime or
module boundary. Future consumers must be reviewed and added individually only
when justified. Narrower operation-specific worker interfaces and stronger module
encapsulation remain possible follow-up hardening. Phase 3C.2 has not started.
