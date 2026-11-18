package com.paymesh.backend.security;

import static org.junit.jupiter.api.Assertions.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.*;

class BoundedRequestBodyFilterTest {
    @Test void acceptsAtLimitAndPreservesEveryByte() throws Exception {
        byte[] expected = "{ \"a\": 1 }".getBytes(StandardCharsets.UTF_8);
        assertArrayEquals(expected, BoundedRequestBodyFilter.readBounded(new ByteArrayInputStream(expected), expected.length));
    }

    @Test void rejectsOversizeEvenWhenLengthIsUnknownAndStopsAfterLimitPlusOne() throws Exception {
        byte[] huge = new byte[2_000_000];
        CountingInput input = new CountingInput(huge);
        assertNull(BoundedRequestBodyFilter.readBounded(input, 4096));
        assertEquals(4097, input.count);
    }

    @Test void returns413BeforeControllerForOversizedDeclaredLength() throws Exception {
        var filter = new BoundedRequestBodyFilter();
        var request = new MockHttpServletRequest("POST", "/api/v1/webhooks/mock-stripe") {
            @Override public long getContentLengthLong() { return 65537; }
        };
        var response = new MockHttpServletResponse();
        filter.doFilter(request, response, (req, res) -> fail("oversized request reached controller"));
        assertEquals(413, response.getStatus());
    }

    @Test void rejectsChunkedStyleUnknownLengthBodyBeforeController() throws Exception {
        var filter = new BoundedRequestBodyFilter();
        var request = new MockHttpServletRequest("POST", "/api/v1/auth/login") {
            @Override public long getContentLengthLong() { return -1; }
        };
        request.setContent(new byte[4097]);
        var response = new MockHttpServletResponse();
        filter.doFilter(request, response, (req, res) -> fail("oversized chunked-style body reached controller"));
        assertEquals(413, response.getStatus());
    }

    private static final class CountingInput extends ByteArrayInputStream {
        int count;
        CountingInput(byte[] bytes) { super(bytes); }
        @Override public synchronized int read(byte[] b, int off, int len) { int n = super.read(b, off, len); if (n > 0) count += n; return n; }
    }
}
