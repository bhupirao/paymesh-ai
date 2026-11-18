import { createInvestigation } from './model.js';
import { renderPairs } from '../components/history.js';
import { renderInvestigation } from './render.js';
import { setText } from '../components/dom.js';
export function mountInvestigation({ onBusy = () => {}, blocked=()=>false } = {}) {
  const $ = id => document.getElementById(id);
  let state, priorBusy = false, priorResult, timer;
  const model = createInvestigation(next => { state = next; render(); },{blocked});
  function tick() {
    clearTimeout(timer);
    const loading = state.phase === 'loading';
    setText($('investigation-elapsed'), loading && state.startedAt !== null ? `Elapsed: ${Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000))} seconds. No estimated progress percentage.` : '');
    if (loading) timer = setTimeout(tick, 1000);
  }
  function render() {
    const loading = state.phase === 'loading';
    $('investigation-result').setAttribute('aria-busy', String(loading));
    $('investigation-phase').className = `status-pill investigation-phase phase-${state.phase}`;
    $('investigation-loading').hidden = !loading;
    $('investigate-button').disabled = !state.available;
    setText($('investigate-button'), state.phase === 'failed' ? 'Retry investigation explicitly' : loading ? 'Investigation in progress…' : state.result ? 'Investigate again with AI' : 'Investigate with AI');
    setText($('investigation-phase'), { ready: 'Ready', loading: 'Loading', completed: 'Completed', inconclusive: 'Inconclusive', failed: 'Failed or unavailable' }[state.phase]);
    setText($('investigation-feedback'), state.message);
    const p = state.payment;
    renderPairs($('investigation-payment'), p ? [['Selected payment UUID',p.paymentId],['Merchant',p.merchantId],['Amount',p.amount],['Currency',p.currency],['Payment method',p.paymentMethod],['Latest authorized payment status',p.status]] : [['Payment','No authorized payment selected.']]);
    if (priorResult !== state.result) { priorResult = state.result; renderInvestigation($('investigation-result'), state.result); }
    tick();
    if (priorBusy !== state.busy) { priorBusy = state.busy; onBusy(state.busy); }
  }
  $('nav-investigation').addEventListener('click', event => {
    event.preventDefault();
    if (state.payment) $('investigation-title').focus();
    else { $('nav-lookup').click(); $('payment-id').focus(); setText($('lookup-feedback'), 'Look up an authorized payment before opening AI Investigation.'); }
  });
  $('investigate-button').addEventListener('click', () => { void model.run(); });
  model.start();
  return { observe: model.observe, busy: model.busy };
}
