// Synthetic unsigned fixture with token-shaped signature. Never an accepted Java credential.
export const paymentId = 'c072351f-4646-4288-b8ca-6758d4e521f3';
export function tokenResponse(roles = ['MERCHANT'], now = Date.now()) {
  const iat = Math.floor(now / 1000);
  const encode = object => btoa(JSON.stringify(object)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  return { tokenType: 'Bearer', expiresIn: 900, expiresAt: new Date((iat + 900) * 1000).toISOString(),
    accessToken: `${encode({ alg: 'RS256' })}.${encode({ sub: paymentId, roles, iat, exp: iat + 900 })}.c3ludGhldGlj` };
}
export function payment() { return { paymentId, merchantId: '<img src=x onerror=alert(1)>', amount: 1000, currency: 'INR', customerId: 'customer', paymentMethod: 'UPI', status: 'SUCCESS', createdAt: '2026-11-14T00:00:00Z' }; }
