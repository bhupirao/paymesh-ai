
package com.paymesh.backend.service;

import com.paymesh.backend.enums.PaymentStatus;
import org.springframework.stereotype.Component;

@Component
public class PaymentStatusTransitionValidator {

    public boolean isAllowed(
            PaymentStatus currentStatus,
            PaymentStatus nextStatus) {

        if (currentStatus == null || nextStatus == null) {
            return false;
        }

        return switch (currentStatus) {

            case CREATED ->
                    nextStatus == PaymentStatus.PROCESSING;

            case PROCESSING ->
                    nextStatus == PaymentStatus.SUCCESS
                            || nextStatus == PaymentStatus.FAILED;

            case SUCCESS, FAILED, CANCELLED, REFUNDED -> false;
        };
    }

    public void validate(
            PaymentStatus currentStatus,
            PaymentStatus nextStatus) {

        if (!isAllowed(currentStatus, nextStatus)) {
            throw new IllegalStateException(
                    "Invalid payment status transition: "
                            + currentStatus + " -> " + nextStatus
            );
        }
    }
}
