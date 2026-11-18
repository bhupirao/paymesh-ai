// All API values are rendered as text; stored exception messages are never shown.
export function renderPairs(container, pairs, doc = document) {
  container.replaceChildren();
  const list = doc.createElement('dl'); list.className = 'payment-fields';
  for (const [label, value] of pairs) {
    const term = doc.createElement('dt'), detail = doc.createElement('dd');
    term.textContent = label; detail.textContent = String(value ?? 'Unavailable'); list.append(term, detail);
  }
  container.append(list);
}
export function safeGatewayError(row) {
  const messages = { INVALID_AMOUNT: 'Invalid amount', UNSUPPORTED_CURRENCY: 'Unsupported currency',
    GATEWAY_EXCEPTION: 'Gateway exception; outcome may be unknown', DEMO_SIMULATED_TIMEOUT: 'Simulated gateway response timeout' };
  if (row.errorCode && Object.hasOwn(messages, row.errorCode)) return `${row.errorCode}: ${messages[row.errorCode]}`;
  return row.errorCode || row.errorMessage ? 'Error details withheld; investigate through authorized operational tooling.' : 'No error recorded';
}
export function renderHistory(container, rows, kind, doc = document) {
  container.replaceChildren();
  if (!rows) return;
  if (!rows.length) { const text = doc.createElement('p'); text.textContent = kind === 'gateway' ? 'No gateway transactions recorded.' : 'No refunds recorded.'; container.append(text); return; }
  const table = doc.createElement('table'); table.className = 'table align-middle history-table';
  const caption = doc.createElement('caption'); caption.textContent = kind === 'gateway' ? 'Actual gateway transaction history' : 'Complete simulated refund history (currency from selected payment)';
  const head = doc.createElement('thead'), header = doc.createElement('tr'), body = doc.createElement('tbody');
  const columns = kind === 'gateway' ? [['gatewayName','Gateway'],['id','Internal UUID'],['gatewayTransactionId','Provider UUID'],['status','Status'],['createdAt','Created (UTC)'],['updatedAt','Updated (UTC)'],['error','Safe error information']] :
    [['refundId','Refund UUID'],['paymentId','Payment UUID'],['amount','Amount'],['status','Status'],['createdAt','Created (UTC)']];
  for (const [, label] of columns) { const cell = doc.createElement('th'); cell.setAttribute('scope', 'col'); cell.textContent = label; header.append(cell); }
  head.append(header);
  for (const row of rows) {
    const tr = doc.createElement('tr');
    for (const [key] of columns) { const cell = doc.createElement('td'); cell.textContent = String(key === 'error' ? safeGatewayError(row) : row[key] ?? 'Unavailable'); tr.append(cell); }
    body.append(tr);
  }
  table.append(caption, head, body); container.append(table);
}
