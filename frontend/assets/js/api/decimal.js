// No Number conversion or arithmetic for payment amounts.
export function decimal(value) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,11})(\.[0-9]{1,2})?$/.test(value)) throw new Error('Use 1–12 integer digits and up to 2 decimal places; minimum 0.01.');
  const [whole, fraction = ''] = value.split('.');
  const normalized = `${whole}.${fraction.padEnd(2, '0')}`;
  if (normalized === '0.00') throw new Error('Amount must be at least 0.01.');
  return normalized;
}
// Scan JSON tokens, preserving amount number lexemes before JSON.parse can round them.
export function parsePaymentJSON(text) {
  let output = '', index = 0;
  while (index < text.length) {
    if (text[index] !== '"') { output += text[index++]; continue; }
    const start = index++;
    while (index < text.length) { if (text[index] === '\\') { index += 2; continue; } if (text[index++] === '"') break; }
    const token = text.slice(start, index); output += token;
    let cursor = index;
    while (/\s/.test(text[cursor] || '') && cursor < text.length) cursor++;
    if (JSON.parse(token) !== 'amount' || text[cursor] !== ':') continue;
    cursor++; while (cursor < text.length && /\s/.test(text[cursor])) cursor++;
    const number = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(cursor));
    if (number) { output += text.slice(index, cursor) + JSON.stringify(number[0]); index = cursor + number[0].length; }
  }
  return JSON.parse(output);
}
export function serializeCreation(body) {
  const amount = decimal(body.amount);
  return `{"merchantId":${JSON.stringify(body.merchantId)},"amount":${amount},"currency":${JSON.stringify(body.currency)},"customerId":${JSON.stringify(body.customerId)},"paymentMethod":${JSON.stringify(body.paymentMethod)}}`;
}

// Refund DTO allows 17 integer digits; payment creation remains limited to 12.
export function refundDecimal(value) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,16})(\.[0-9]{1,2})?$/.test(value)) throw new Error('Invalid refund amount');
  const [whole, fraction = ''] = value.split('.');
  const normalized = `${whole}.${fraction.padEnd(2, '0')}`;
  if (normalized === '0.00') throw new Error('Invalid refund amount');
  return normalized;
}
export function minorUnits(value, refund = false) {
  return BigInt((refund ? refundDecimal(value) : decimal(value)).replace('.', ''));
}
export function formatMinor(value) {
  if (typeof value !== 'bigint' || value < 0n) throw new Error('Invalid minor units');
  return `${value / 100n}.${String(value % 100n).padStart(2, '0')}`;
}
export function serializeRefund(body) { return `{"amount":${refundDecimal(body.amount)}}`; }

export function serializeLink(body){if(!Number.isInteger(body.expiryHours)||![1,24,168].includes(body.expiryHours))throw new Error('Invalid link expiry');return `{"amount":${decimal(body.amount)},"currency":${JSON.stringify(body.currency)},"paymentMethod":${JSON.stringify(body.paymentMethod)},"customerReference":${JSON.stringify(body.customerReference)},"description":${JSON.stringify(body.description)},"expiryHours":${body.expiryHours}}`;}
