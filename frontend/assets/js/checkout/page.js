import { mountCheckout } from './view.js';
const root=document.getElementById('customer-checkout');let page;
function start(){const match=/^\/checkout\/([A-Za-z0-9_-]{43})$/.exec(window.location.pathname);if(!match){root.textContent='Checkout unavailable.';return;}page=mountCheckout(root,match[1]);void page.start();}
start();
window.addEventListener('pagehide',()=>page?.dispose());
window.addEventListener('pageshow',event=>{if(event.persisted)start();});
