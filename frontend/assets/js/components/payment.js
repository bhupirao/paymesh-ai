const fields = [['paymentId','Payment ID'],['merchantId','Merchant ID'],['amount','Amount'],['currency','Currency'],['customerId','Customer ID'],['paymentMethod','Payment method'],['status','Status'],['createdAt','Created at (ISO 8601)']];
function renderFields(container, payment, selected, doc) {
  container.replaceChildren();
  if (!payment) return;
  const list = doc.createElement('dl'); list.className = 'payment-fields';
  for (const [key, label] of selected) {
    const term = doc.createElement('dt'), value = doc.createElement('dd');
    term.textContent = label; value.textContent = String(payment[key] ?? 'Unavailable');
    list.append(term, value);
  }
  container.append(list);
}

export function renderPayment(container, payment, doc = document) { renderFields(container, payment, fields, doc); }
export function renderIntent(container, intent, doc = document) { renderFields(container, intent, fields.filter(([key]) => ['merchantId', 'amount', 'currency', 'customerId', 'paymentMethod'].includes(key)), doc); }
