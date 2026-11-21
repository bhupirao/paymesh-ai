import { test, expect, ORIGIN, accounts, credential, newPage, login, responseFor, body, modelSuccess, requireSafe, noOverflow, openHistory, safeDialog, exactAmount, logout, navigate, refreshPage, authAction, checkpoint, chatWitness } from './fixtures.js';

test('COMPLETE_NATIVE_BROWSER_JOURNEY', async ({ browser }) => {
  test.setTimeout(900_000); // Includes bounded admission waits for the unchanged 60s auth limiter.
  const sessions = await Promise.all([newPage(browser), newPage(browser), newPage(browser), newPage(browser)]);
  const [merchant, other, admin, customer] = sessions;
  let merchantId, paymentId;
  try {
    await test.step('MERCHANT_REGISTRATION_VALIDATION', async () => {
      for (const [actor, key] of [[merchant,'a'],[other,'b']]) {
        const p = actor.page;
        await navigate(p,'/merchant/signup');
        await p.locator('#signup-check').click();
        await expect(p.locator('#signup-feedback')).toContainText('Check the highlighted fields');
        for (const [field,value] of Object.entries({firstName:'Browser',lastName:key,businessName:`Disposable browser ${key}`,email:accounts[key],mobile:'+12025550101'})) await p.locator(`#signup-${field}`).fill(value);
        await p.locator('#signup-businessType').selectOption('COMPANY');
        await p.locator('#signup-country').selectOption('US');
        const password=credential('merchant_password');
        await p.locator('#signup-password').fill(password);
        await p.locator('#signup-confirmPassword').fill(password);
        await p.locator('#signup-terms').check();
        let reply;
        await authAction(p,'/api/v1/auth/register',async()=>{reply=responseFor(p,'POST','/api/v1/auth/register');await p.locator('#signup-check').click();});
        requireSafe((await body(await reply,[201])).accountStatus==='PENDING_APPROVAL','REGISTRATION_STATUS');
        await expect(p.locator('#signup-success-link')).toBeVisible();
      }
      await login(merchant.page,'merchant','a');
      await expect(merchant.page.locator('#pending-onboarding')).toBeVisible();
      await logout(merchant.page);
      await expect(merchant.page.locator('#login-form')).toBeVisible();
    });
    await test.step('ADMIN_LOGIN_AND_NATIVE_APPROVAL', async () => {
      await checkpoint('ADMIN_LOGIN_STARTED',()=>login(admin.page,'admin','admin'));
      await checkpoint('ADMIN_DASHBOARD_VISIBLE',()=>expect(admin.page.locator('#admin-workspace')).toBeVisible());
      for (const key of ['a','b']) {
        const p=admin.page;
        await checkpoint('MERCHANT_SEARCH_STARTED',()=>navigate(p,'/admin/merchants'));
        const root=p.locator('#admin-workspace');
        await expect(root.getByRole('button',{name:'Apply / Look up',exact:true})).toBeEnabled();
        await checkpoint('MERCHANT_SEARCH_INPUT',()=>root.getByLabel('Search',{exact:true}).fill(accounts[key]));
        const list=responseFor(p,'GET','/api/v1/admin/merchants');
        const rows=(await checkpoint('MERCHANT_SEARCH_COMPLETED',async()=>{
          await root.getByRole('button',{name:'Apply / Look up',exact:true}).click();
          return body(await list);
        })).items;
        requireSafe(rows.length===1,'UNIQUE_PENDING_MERCHANT_REQUIRED');
        if(key==='a') merchantId=rows[0].merchantId;
        await checkpoint('MERCHANT_DETAIL_OPENED',async()=>{
          await root.getByRole('row').filter({hasText:accounts[key]}).getByRole('button',{name:'Open',exact:true}).click();
          await expect(p).toHaveURL(ORIGIN+'/admin/merchant');
          await expect(root.getByLabel('External ownership review reference')).toBeVisible();
        });
        await checkpoint('APPROVAL_REVIEW_FILLED',async()=>{
          await root.getByLabel('External ownership review reference').fill('CI-BROWSER-OWNERSHIP');
          await root.getByLabel('I attest that ownership was reviewed for this exact Merchant.').check();
        });
        const dialog=root.getByRole('dialog',{name:'Confirm Merchant administration'});
        await checkpoint('APPROVAL_DIALOG_OPENED',async()=>{
          await root.getByRole('button',{name:'Review approve',exact:true}).click();
          await expect(dialog).toBeFocused();
        });
        await checkpoint('APPROVAL_CANCELLED',()=>dialog.getByRole('button',{name:'Cancel review',exact:true}).click());
        await expect(dialog).toHaveCount(0);
        await checkpoint('APPROVAL_REVIEW_FILLED',async()=>{
          await root.getByLabel('External ownership review reference').fill('CI-BROWSER-OWNERSHIP');
          await root.getByLabel('I attest that ownership was reviewed for this exact Merchant.').check();
        });
        await checkpoint('APPROVAL_DIALOG_OPENED',async()=>{
          await root.getByRole('button',{name:'Review approve',exact:true}).click();
          await expect(dialog).toBeFocused();
        });
        const approved=responseFor(p,'POST','/api/v1/admin/merchant/approve');
        await checkpoint('APPROVAL_SUBMITTED',()=>root.getByRole('dialog').getByRole('button',{name:'Confirm approve',exact:true}).click());
        const active=await checkpoint('APPROVAL_CONFIRMED',async()=>body(await approved));
        requireSafe(active.merchantId===rows[0].merchantId&&active.status==='ACTIVE','APPROVAL_STATE_REQUIRED');
        await expect(root.getByLabel('External ownership review reference')).toHaveCount(0);
      }
      await checkpoint('ACTIVE_MERCHANT_LOGIN',async()=>{await login(merchant.page,'merchant','a');await login(other.page,'merchant','b');});
      await expect(merchant.page.locator('#pending-onboarding')).toBeHidden();
    });
    await test.step('DASHBOARD_SESSION_AND_ROLE_PROTECTION', async () => {
      const p=merchant.page;
      await expect(p.locator('#merchant-workspace')).toBeVisible();
      await refreshPage(p);
      await expect(p.locator('#merchant-workspace')).toBeVisible();
      await p.setViewportSize({width:375,height:812});await noOverflow(p);
      await p.setViewportSize({width:1440,height:1000});
      await navigate(p,'/admin/dashboard');
      await expect(p.locator('#login-form')).toBeVisible();
      await expect(p.locator('#admin-workspace')).toBeHidden();
      await navigate(p,'/merchant/dashboard');
      await expect(p.locator('#merchant-workspace')).toBeVisible();
      await navigate(admin.page,'/merchant/dashboard');
      await expect(admin.page.locator('#merchant-workspace')).toBeHidden();
      await navigate(admin.page,'/admin/dashboard');
      await expect(admin.page.locator('#admin-workspace')).toBeVisible();
      await admin.page.setViewportSize({width:375,height:812});await noOverflow(admin.page);
      await admin.page.setViewportSize({width:1440,height:1000});
    });
    await test.step('PAYMENT_CREATION_PROCESSING_AND_LIST', async () => {
      const p=merchant.page;
      await p.locator('#nav-create').click();
      await expect(p.locator('#create-form')).toBeVisible();
      for(const [id,value] of [['merchant-id',merchantId],['create-amount','13.25'],['customer-id','browser-synthetic-order'],['payment-method','UPI']]) await p.locator('#'+id).fill(value);
      await p.locator('#create-currency').selectOption('INR');
      await p.locator('#review-create').click();
      await expect(p.locator('#creation-review')).toBeVisible();
      await expect(p.locator('#creation-review')).toContainText('13.25');
      const created=responseFor(p,'POST','/api/v1/payments');
      const payment=await checkpoint('PAYMENT_CREATED',async()=>{await p.locator('#confirm-create').click();return body(await created,[201]);});paymentId=payment.paymentId;
      requireSafe(payment.status==='CREATED'&&String(payment.amount)==='13.25','CREATED_PAYMENT_CONTRACT');
      await expect(p.locator('#created-result')).toContainText(paymentId);
      await p.locator('#created-process').click();
      await expect(p.locator('#process-panel')).toBeVisible();
      await p.locator('#cancel-process').click();
      await expect(p.locator('#process-panel')).toBeHidden();
      await p.locator('#created-process').click();
      const processed=responseFor(p,'POST',`/api/v1/payments/${paymentId}/process`);
      const processedPayment=await checkpoint('PAYMENT_PROCESSED',async()=>{await p.locator('#confirm-process').click();return body(await processed);});
      requireSafe(processedPayment.status==='SUCCESS','PAYMENT_PROCESSING_STATUS');
      await checkpoint('PAYMENT_LIST_OPENED',()=>navigate(p,'/merchant/payments'));
      await expect(p.locator('#merchant-workspace').getByRole('row').filter({hasText:paymentId})).toContainText('SUCCESS');
      await p.locator('#merchant-workspace').getByRole('row').filter({hasText:paymentId}).getByRole('button',{name:'Open payment',exact:true}).click();
      await expect(p.locator('#details-id')).toHaveText(paymentId);
    });
    await test.step('MERCHANT_OWNERSHIP_ISOLATION', async () => {
      const p=other.page;
      await p.locator('#nav-lookup').click();
      await p.locator('#payment-id').fill(paymentId);
      const denied=responseFor(p,'GET',`/api/v1/payments/${paymentId}`);
      const denial=await checkpoint('OWNERSHIP_DENIAL',async()=>{await p.locator('#lookup-submit').click();return denied;});
      requireSafe([403,404].includes(denial.status()),'OWNERSHIP_DENIAL_REQUIRED');
      await expect(p.locator('#lookup-feedback')).toContainText(/not accessible|not permitted|Access denied/i);
      await expect(p.locator('#payment-result')).toBeEmpty();
    });
    await test.step('NATIVE_INVESTIGATION_REAL_QWEN', async () => {
      const p=merchant.page;
      await expect(p.locator('#investigate-button')).toBeEnabled();
      const reply=responseFor(p,'POST',`/api/v1/payments/${paymentId}/investigate`);
      const result=modelSuccess(await checkpoint('INVESTIGATION_SUBMITTED',async()=>{await p.locator('#investigate-button').click();return body(await reply);}));
      requireSafe(result.paymentId===paymentId,'INVESTIGATION_SCOPE');
      await expect(p.locator('#investigation-result')).toBeVisible();
      await expect(p.locator('#investigation-result')).toContainText('Customer view');
    });
    await test.step('PARTIAL_AND_FULL_REFUND_UI', async () => {
      const p=merchant.page;
      for(const [amount,total] of [['3.25','3.25'],['10.00','13.25']]) {
        await p.locator('#refresh-details').click();
        await expect(p.locator('#refund-amount')).toBeEnabled();
        await p.locator('#refund-amount').fill(amount);
        await p.locator('#refund-form').getByRole('button',{name:'Review refund',exact:true}).click();
        await expect(p.locator('#refund-review')).toBeFocused();
        const refunded=responseFor(p,'POST',`/api/v1/payments/${paymentId}/refund`);
        const result=await checkpoint('REFUND_SUBMITTED',async()=>{await p.locator('#confirm-refund').click();return body(await refunded,[201]);});
        requireSafe(result.status==='SUCCESS'&&exactAmount(result.amount)===amount,'REFUND_RECORD');
        await expect(p.locator('#confirmed-refund')).toBeVisible();
        await expect(p.locator('#refund-summary')).toContainText(total+' INR');
      }
      await expect(p.locator('#details-overview-result')).toContainText('REFUNDED');
      await expect(p.locator('#refund-summary')).toContainText('0.00 INR');
      await p.setViewportSize({width:375,height:812});await noOverflow(p);
      await p.setViewportSize({width:1440,height:1000});
    });
    await test.step('PAYMENT_LINK_AND_CUSTOMER_CHECKOUT', async () => {
      const p=merchant.page;
      await navigate(p,'/merchant/payment-links/create');
      const root=p.locator('#merchant-links-workspace');
      await checkpoint('CHECKOUT_FORM_READY',async()=>{await expect(root).toBeVisible();await expect(root.locator('input[name="amount"]')).toBeVisible();},{page:p,expectedState:'LINK_CREATE_FORM'});
      await checkpoint('CHECKOUT_CURRENCY_SELECTED',async()=>{
        const currency=root.locator('select[name="currency"]');await currency.selectOption('USD');await expect(currency).toHaveValue('USD');
      },{page:p,expectedState:'LINK_CREATE_FORM'});
      await root.getByLabel('Amount',{exact:true}).fill('25.00');
      await checkpoint('CHECKOUT_METHOD_SELECTED',async()=>{
        const method=root.locator('select[name="paymentMethod"]');await method.selectOption('CARD');await expect(method).toHaveValue('CARD');
      },{page:p,expectedState:'LINK_CREATE_FORM'});
      await root.getByLabel('Customer / order reference (optional)').fill('browser-checkout');
      await checkpoint('CHECKOUT_REVIEW_OPENED',async()=>{await root.getByRole('button',{name:'Review link',exact:true}).click();await expect(root.getByRole('button',{name:'Confirm create payment link',exact:true})).toBeVisible();},{page:p,expectedState:'LINK_REVIEW'});
      const created=responseFor(p,'POST','/api/v1/merchant/payment-links');
      const link=await checkpoint('CHECKOUT_LINK_CREATED',async()=>{await root.getByRole('button',{name:'Confirm create payment link',exact:true}).click();return body(await created,[201]);},{page:p,expectedState:'LINK_CREATED',expectedHttp:'LINK_CREATE'});
      requireSafe(link.status==='ACTIVE'&&link.amount==='25.00'&&link.currency==='USD'&&link.paymentMethod==='CARD'&&/^[0-9a-f-]{36}$/.test(link.linkId),'CHECKOUT_LINK_CONTRACT');
      const url=await root.getByLabel('Customer checkout URL (simulation only)').inputValue();
      requireSafe(new URL(url).origin===ORIGIN&&/^\/checkout\/[A-Za-z0-9_-]{43}$/.test(new URL(url).pathname),'FIXED_CHECKOUT_URL');
      const c=customer.page;
      await checkpoint('CUSTOMER_CHECKOUT_OPENED',async()=>{
        const read=responseFor(c,'GET',/^\/api\/v1\/checkout\/[A-Za-z0-9_-]{43}\/status$/);
        await navigate(c,url);const checkout=await body(await read);
        requireSafe(checkout.checkoutStatus==='ACTIVE'&&checkout.canPay===true&&checkout.amount==='25.00'&&checkout.currency==='USD'&&checkout.paymentMethod==='CARD','CHECKOUT_READ_CONTRACT');
        await expect(c.getByRole('heading',{name:'PayMesh AI · Customer checkout'})).toBeVisible();
      },{page:c,expectedState:'PUBLIC_CHECKOUT',expectedHttp:'CHECKOUT_READ'});
      await expect(c.getByRole('heading',{name:'PayMesh AI · Customer checkout'})).toBeVisible();
      await expect(c.getByText('25.00 USD',{exact:true})).toBeVisible();
      await expect(c.getByText('CARD',{exact:true})).toBeVisible();
      await checkpoint('CUSTOMER_PAYMENT_REVIEWED',()=>c.getByRole('button',{name:'Pay — review simulated payment',exact:true}).click(),{page:c,expectedState:'PAYMENT_REVIEW'});
      await expect(c.getByRole('heading',{name:'Confirm simulated payment',exact:true})).toBeFocused();
      await c.getByRole('button',{name:'Back to checkout',exact:true}).click();
      await checkpoint('CUSTOMER_PAYMENT_REVIEWED',()=>c.getByRole('button',{name:'Pay — review simulated payment',exact:true}).click(),{page:c,expectedState:'PAYMENT_REVIEW'});
      const paid=responseFor(c,'POST',/^\/api\/v1\/checkout\/[A-Za-z0-9_-]{43}\/pay$/);
      const receipt=await checkpoint('CHECKOUT_SUBMITTED',async()=>{await c.getByRole('button',{name:'Confirm Pay (simulation only)',exact:true}).click();return body(await paid);},{page:c,expectedState:'PAID_RECEIPT',expectedHttp:'CHECKOUT_PAY'});
      requireSafe(receipt.checkoutStatus==='PAID','PAID_CHECKOUT_REQUIRED');
      await checkpoint('CHECKOUT_RECEIPT_VISIBLE',()=>expect(c.getByRole('heading',{name:'Simulated payment receipt',exact:true})).toBeVisible(),{page:c,expectedState:'PAID_RECEIPT'});
      await checkpoint('CHECKOUT_RECEIPT_VISIBLE',async()=>{
        const read=responseFor(c,'GET',/^\/api\/v1\/checkout\/[A-Za-z0-9_-]{43}\/status$/);await refreshPage(c);
        requireSafe((await body(await read)).checkoutStatus==='PAID','PAID_CHECKOUT_REQUIRED');
        await expect(c.getByRole('heading',{name:'Simulated payment receipt',exact:true})).toBeVisible();
      },{page:c,expectedState:'PAID_RECEIPT',expectedHttp:'CHECKOUT_READ'});
      await c.setViewportSize({width:375,height:812});await noOverflow(c);
      let paidLink;
      await checkpoint('CHECKOUT_MERCHANT_STATUS_CONFIRMED',async()=>{
        const read=responseFor(p,'GET',`/api/v1/merchant/payment-links/${link.linkId}`);
        await root.getByRole('button',{name:'Refresh link',exact:true}).click();paidLink=await body(await read);
        requireSafe(paidLink.status==='PAID'&&paidLink.amount==='25.00'&&paidLink.currency==='USD'&&/^[0-9a-f-]{36}$/.test(paidLink.paymentId),'PAID_LINK_REQUIRED');
      },{page:p,expectedState:'MERCHANT_PAID_LINK',expectedHttp:'LINK_READ'});
      await checkpoint('CHECKOUT_PAYMENT_AVAILABLE',async()=>{
        const paymentRead=responseFor(p,'GET',`/api/v1/payments/${paidLink.paymentId}`);
        await root.getByRole('button',{name:'Open authorized payment',exact:true}).click();
        const linkedPayment=await body(await paymentRead);requireSafe(linkedPayment.status==='SUCCESS'&&exactAmount(linkedPayment.amount)==='25.00'&&linkedPayment.currency==='USD','CHECKOUT_PAYMENT_CONTRACT');
        await expect(p.locator('#details-id')).toHaveText(paidLink.paymentId);await expect(p.locator('#refund-amount')).toBeEnabled();
        await expect(p.locator('#refund-summary')).toContainText('25.00 USD');
      },{page:p,expectedState:'MERCHANT_PAID_LINK',expectedHttp:'PAYMENT_READ'});
    });
    await test.step('MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY', async () => {
      for(const [actor,role] of [[merchant,'merchant'],[admin,'admin']]) {
        const p=actor.page;let submissions=0;
        const observe=req=>{if(req.method()==='POST'&&/^\/api\/v1\/(merchant|admin)\/ai\/(chat|conversations(?:\/[^/]+\/messages)?)$/.test(new URL(req.url()).pathname))submissions++;};
        p.on('request',observe);
        try {
          await navigate(p,`/${role}/ai`);
          const root=p.locator(`#${role}-ai-workspace`),composer=root.getByLabel('Your payment-domain question');
          await expect(composer).toBeEnabled({timeout:25_000});requireSafe(submissions===0,'AUTOMATIC_AI_REQUEST');
          await composer.fill('What is idempotency?');
          await composer.press('Shift+Enter');
          await expect(composer).toHaveValue('What is idempotency?\n');
          requireSafe(submissions===0,'SHIFT_ENTER_SENT_QUESTION');
          chatWitness(false,false); // Reset per portal/request; never reuse a prior chat witness.
          const reply=responseFor(p,'POST',new RegExp(`^/api/v1/${role}/ai/conversations/[^/]+/messages$`));
          modelSuccess(await checkpoint('CHAT_SUBMITTED',async()=>{
            if(role==='merchant')await composer.press('Enter');else await root.getByRole('button',{name:'Send question',exact:true}).click();
            return body(await reply);
          },{page:p,expectedState:'CHAT_ANSWER',expectedHttp:'CHAT_MESSAGE'}));
          chatWitness(true,false); // Parsed response passed the strict real-model checks above.
          await checkpoint('CHAT_ANSWER_RENDERED',async()=>{
            await expect(root.locator('.ai-assistant .ai-answer')).toBeVisible();
            requireSafe((await root.locator('.ai-assistant .ai-answer').innerText()).trim().length>0,'VISIBLE_ANSWER_REQUIRED');
            chatWitness(true,true);
          },{page:p,expectedState:'CHAT_ANSWER'});
          await checkpoint('HISTORY_TITLE_FILLED',async()=>{
            await openHistory(root);
            const title=root.getByLabel('Conversation title',{exact:true});
            await expect(title).toBeVisible();
            await expect(title).toBeEnabled();
            await title.fill(`Browser ${role} history`);
          },{page:p,expectedState:'SAVED_HISTORY'});
          const renamed=responseFor(p,'POST',new RegExp(`^/api/v1/${role}/ai/conversations/[^/]+/rename$`));
          await checkpoint('HISTORY_RENAMED',async()=>{await root.getByRole('button',{name:'Rename saved conversation',exact:true}).click();return body(await renamed);},{page:p,expectedState:'SAVED_HISTORY',expectedHttp:'HISTORY_RENAME'});
          await expect(root.locator('.conversation-history')).toContainText(`Current: Browser ${role} history`);
          await root.getByLabel('Search owned conversation titles').fill(`Browser ${role} history`);
          const ownList=responseFor(p,'GET',`/api/v1/${role}/ai/conversations`);
          const owned=await checkpoint('HISTORY_LISTED',async()=>{await root.getByRole('button',{name:'Load saved conversations',exact:true}).click();return body(await ownList);});
          requireSafe(owned.total===1,'OWNED_HISTORY_SEARCH');
          const selected=root.getByRole('button',{name:`Browser ${role} history · Current`,exact:true});
          await expect(selected).toBeVisible();
          const historyRead=responseFor(p,'GET',new RegExp(`^/api/v1/${role}/ai/conversations/[^/]+/messages$`));
          const saved=await checkpoint('HISTORY_LOADED',async()=>{await safeDialog(p,()=>selected.click());return body(await historyRead);},{page:p,expectedState:'SAVED_HISTORY',expectedHttp:'HISTORY_READ'});
          requireSafe(saved.total===1,'SAVED_TURN_REQUIRED');
          await expect(root.locator('.ai-assistant .ai-answer')).toBeVisible();
          const before=submissions;
          await checkpoint('HISTORY_REFRESHED',async()=>{
            await refreshPage(p);
            // Intentionally retain the released-application requirement. The
            // source audit finds this deep-link restoration currently broken;
            // never turn it into an explicit-load workaround or silent pass.
            await expect(p).toHaveURL(ORIGIN+`/${role}/ai`);
            await expect(root.locator('.ai-assistant .ai-answer')).toBeVisible();
          },{page:p,expectedState:'SAVED_HISTORY'});
          requireSafe(submissions===before,'RESTORE_INVOKED_MODEL');
          if(role==='merchant') {
            await navigate(other.page,'/merchant/ai');
            const otherRoot=other.page.locator('#merchant-ai-workspace');
            await expect(otherRoot.getByLabel('Your payment-domain question')).toBeEnabled();await openHistory(otherRoot);
            const otherList=responseFor(other.page,'GET','/api/v1/merchant/ai/conversations');
            await otherRoot.getByRole('button',{name:'Load saved conversations',exact:true}).click();
            requireSafe((await body(await otherList)).total===0,'OTHER_MERCHANT_PRIVATE_HISTORY');
            await expect(otherRoot.locator('.conversation-history')).toContainText('0 accessible matches');
            await expect(otherRoot.getByRole('button',{name:/Browser merchant history/})).toHaveCount(0);
            // Admin has its own private history while this Merchant turn exists.
            await navigate(admin.page,'/admin/ai');
            const adminRoot=admin.page.locator('#admin-ai-workspace');
            await expect(adminRoot.getByLabel('Your payment-domain question')).toBeEnabled();
            await openHistory(adminRoot);
            const adminList=responseFor(admin.page,'GET','/api/v1/admin/ai/conversations');
            await adminRoot.getByRole('button',{name:'Load saved conversations',exact:true}).click();
            requireSafe((await body(await adminList)).total===0,'ADMIN_MERCHANT_HISTORY_ISOLATION');
            await expect(adminRoot.getByRole('button',{name:/Browser merchant history/})).toHaveCount(0);
          }
          await p.setViewportSize({width:375,height:812});await noOverflow(p);
          await p.setViewportSize({width:1440,height:1000});
          await openHistory(root);
          const deleted=responseFor(p,'POST',new RegExp(`^/api/v1/${role}/ai/conversations/[^/]+/delete$`));
          await checkpoint('HISTORY_DELETED',async()=>{await safeDialog(p,()=>root.getByRole('button',{name:'Delete saved conversation',exact:true}).click());return body(await deleted);},{page:p,expectedState:'SAVED_HISTORY',expectedHttp:'HISTORY_DELETE'});
          await expect(root.locator('.conversation-history')).toContainText('No saved conversation selected');
          await expect(root.locator('.ai-assistant')).toHaveCount(0);
        } finally {p.off('request',observe);}
      }
    });
    await test.step('CROSS_TAB_LOGOUT_AND_PROTECTED_ROUTE', async () => {
      const p=merchant.page,tab=await merchant.context.newPage();
      await checkpoint('CROSS_TAB_RESTORED',async()=>{await navigate(tab,'/merchant/dashboard');await expect(tab.locator('#merchant-workspace')).toBeVisible();});
      await logout(p);
      await expect(p.locator('#login-form')).toBeVisible();
      await expect(tab.locator('#login-form')).toBeVisible();
      await expect(tab.locator('#merchant-workspace')).toBeHidden();
      await navigate(tab,'/merchant/ai');await expect(tab.locator('#login-form')).toBeVisible();
      await tab.close();
      await logout(admin.page);await expect(admin.page.locator('#login-form')).toBeVisible();
      await logout(other.page);await expect(other.page.locator('#login-form')).toBeVisible();
    });
  } finally {
    for(const actor of sessions) await actor.context.close();
  }
});
