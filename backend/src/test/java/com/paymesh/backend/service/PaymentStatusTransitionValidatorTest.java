
package com.paymesh.backend.service;

import com.paymesh.backend.enums.PaymentStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class PaymentStatusTransitionValidatorTest {

    private PaymentStatusTransitionValidator validator;

    @BeforeEach
    void setUp() {
        validator = new PaymentStatusTransitionValidator();
    }

    @Test
    void shouldAllowCreatedToProcessing() {
        assertTrue(validator.isAllowed(
                PaymentStatus.CREATED,
                PaymentStatus.PROCESSING
        ));
    }

    @Test
    void shouldAllowProcessingToSuccess() {
        assertTrue(validator.isAllowed(
                PaymentStatus.PROCESSING,
                PaymentStatus.SUCCESS
        ));
    }

    @Test
    void shouldAllowProcessingToFailed() {
        assertTrue(validator.isAllowed(
                PaymentStatus.PROCESSING,
                PaymentStatus.FAILED
        ));
    }

    @Test
    void shouldRejectCreatedToSuccess() {
        assertFalse(validator.isAllowed(
                PaymentStatus.CREATED,
                PaymentStatus.SUCCESS
        ));
    }

    @Test
    void shouldRejectSuccessToProcessing() {
        assertFalse(validator.isAllowed(
                PaymentStatus.SUCCESS,
                PaymentStatus.PROCESSING
        ));
    }

    @Test
    void shouldRejectFailedToSuccess() {
        assertFalse(validator.isAllowed(
                PaymentStatus.FAILED,
                PaymentStatus.SUCCESS
        ));
    }

    @Test
    void shouldRejectSameStatusTransition() {
        assertFalse(validator.isAllowed(
                PaymentStatus.PROCESSING,
                PaymentStatus.PROCESSING
        ));
    }

    @Test
    void shouldRejectNullStatus() {
        assertFalse(validator.isAllowed(
                null,
                PaymentStatus.PROCESSING
        ));
    }

    @Test
    void shouldThrowExceptionForInvalidTransition() {
        IllegalStateException exception = assertThrows(
                IllegalStateException.class,
                () -> validator.validate(
                        PaymentStatus.SUCCESS,
                        PaymentStatus.PROCESSING
                )
        );

        assertTrue(exception.getMessage()
                .contains("Invalid payment status transition"));
    }

    @Test
    void shouldNotThrowExceptionForValidTransition() {
        assertDoesNotThrow(() -> validator.validate(
                PaymentStatus.CREATED,
                PaymentStatus.PROCESSING
        ));
    }
}
