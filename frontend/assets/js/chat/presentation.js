import { request } from '../api/client.js';
import { createConversationStore } from '../conversations/store.js';
import { createHistoryView } from '../conversations/view.js';
import { element } from '../admin/view.js';
import { chatButton as button,renderAnswer } from './render.js';
export function mountConversation(root,{titleText,titleId,helpId,modelFactory,createContext,welcome,emptyText='Welcome. Choose a context and ask explicitly. No AI request runs when this page opens.',allowCancel=false,openPayment,locked=()=>false,onBusy=()=>{},api,savedConversations=api===undefined,conversationScope,confirm=message=>window.confirm(message)}={}){
 let state,visible=false,timer,rendered='',model,history,store;
 const externalLocked=locked;locked=()=>externalLocked()||Boolean(store?.blocked());
 const newChat=()=>{if((state.turns.length||state.busy)&&!confirm('Clear this conversation and invalidate any pending response? The request may still finish.'))return;store?.newChat();model.restart();contextUI.clear();composer.value='';composer.focus();};
 if(savedConversations)store=createConversationStore({api:api||request,adopt:data=>{const ok=model.restore(data);if(ok)queueMicrotask(()=>{if(visible&&state?.eligible)composer.focus();});return ok;},onDeny:()=>model?.clear(),onForget:()=>model?.forget(),canReplace:()=>!externalLocked()&&(!(state?.turns.length||state?.busy)||confirm('Replace displayed conversation? Pending inference may still finish.')),onChange:next=>{history?.render(next);if(state){composer.disabled=send.disabled=state.busy||!state.eligible||locked();retry.disabled=state.busy||locked();}}});
 root.className=(root.className||'')+' merchant-ai';root.hidden=true;
 const title=element('h2',titleText);title.tabIndex=-1;title.id=titleId;
 const notice=element('p','Recorded evidence only. AI cannot execute financial operations or confirm bank debit, settlement or refund arrival. Do not enter passwords, tokens, personal contact details or raw identifiers.','ai-notice');
 const message=element('p');message.setAttribute('role','status');message.setAttribute('aria-live','polite');message.setAttribute('aria-atomic','true');
 const tools=element('div',undefined,'ai-actions');const reset=button('New Chat',newChat);tools.append(reset);const cancel=allowCancel?button('Cancel pending analysis',()=>{if(confirm('Stop waiting and ignore this reply? The request may still finish.'))model.cancel();}):null;if(cancel)tools.append(cancel);
 const contextUI=createContext({getModel:()=>model,change:action=>changeContext(action),locked});const context=contextUI.root;
 const transcript=element('div',undefined,'ai-conversation');transcript.setAttribute('role','region');transcript.setAttribute('aria-label','Private current-session conversation');transcript.tabIndex=0;
 const suggestions=element('div',undefined,'ai-actions');
 const progress=element('div');progress.setAttribute('role','status');const elapsed=element('span');elapsed.setAttribute('role','timer');elapsed.setAttribute('aria-live','off');progress.append(element('span','Analysis in progress. '),elapsed);progress.hidden=true;
 const retry=button('Retry failed question explicitly',()=>void model.retry());retry.hidden=true;
 const form=element('form',undefined,'ai-composer');const composeLabel=element('label','Your payment-domain question');const composer=element('textarea');composer.rows=3;composer.className='form-control';composer.setAttribute('aria-describedby',helpId);composeLabel.append(composer);const help=element('p','Maximum 1,000 Unicode characters. Enter sends; Shift+Enter adds a newline. Up to four completed recent turns within the server history limits are included. Long answers are omitted from history as whole turns.','small');help.id=helpId;const send=element('button','Send question','btn btn-primary');send.type='submit';form.append(composeLabel,help,send);
 const submit=async()=>{const q=composer.value;const work=model.send(q);if(model.state().busy)composer.value='';await work;if(visible&&!state.busy)composer.focus();};form.addEventListener('submit',e=>{e.preventDefault();void submit();});composer.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();void submit();}});
 if(store){history=createHistoryView({store,confirm,canManage:()=>!externalLocked()&&!state?.busy,onNew:newChat});history.render(store.state());}
 root.append(title,notice,...(history?[history.root]:[]),message,tools,context,suggestions,transcript,progress,retry,form);
 function changeContext(action){if((state.turns.length||state.busy)&&!confirm('Replace context and clear this conversation? Any pending response will be ignored; the request may still finish.'))return;if(action()){contextUI.replaced?.();composer.value='';composer.focus();}}
 function tick(){clearTimeout(timer);if(visible&&state?.busy){elapsed.textContent=`Elapsed ${Math.max(0,Math.floor((Date.now()-state.startedAt)/1000))} seconds. No estimated progress.`;timer=setTimeout(tick,1000);}else elapsed.textContent='';}
 function render(next){state=next;store?.setScope(state.eligible?conversationScope?.(state):null);if(state.eligible&&store)queueMicrotask(()=>{if(visible&&state?.eligible)void store.restoreLast();});const allowed=state.eligible;root.hidden=!visible;message.textContent=state.message+((!store&&state.turns.length>=20)?' The 20-turn memory limit is reached. Use New Chat for a new question; a failed last question can still be retried.':'');context.hidden=form.hidden=suggestions.hidden=!allowed;
  if(!allowed){composer.value='';contextUI.clear();transcript.replaceChildren();rendered='';}
  composer.disabled=send.disabled=state.busy||!allowed||locked()||(!store&&state.turns.length>=20);send.textContent=state.busy?'Sending…':'Send question';form.setAttribute('aria-busy',String(state.busy));progress.hidden=!state.busy;retry.hidden=!state.failedQuestion||!allowed;retry.disabled=state.busy||locked();reset.disabled=state.checking;if(cancel)cancel.hidden=!state.busy;
  suggestions.replaceChildren();for(const q of welcome(state)){const b=button(`Ask: ${q}`,()=>void model.send(q));b.disabled=state.busy||locked();suggestions.append(b);}suggestions.hidden=!allowed||state.turns.length>0;contextUI.render(state);
  const signature=JSON.stringify(state.turns);if(signature!==rendered){rendered=signature;transcript.replaceChildren();
   if(!state.turns.length)transcript.append(element('p',emptyText));
   for(const turn of state.turns){const user=element('article',undefined,'ai-bubble ai-user');user.append(element('h3','You'),element('p',turn.question));transcript.append(user);
    if(turn.status==='completed'){const assistant=element('article',undefined,'ai-bubble ai-assistant');assistant.append(element('h3','PayMesh AI'));renderAnswer(assistant,turn.result,{ask:q=>void model.send(q),openPayment,canAct:()=>visible&&state.eligible&&!state.busy&&!locked()&&assistant.parentNode===transcript,announce:text=>{if(visible&&state.eligible)message.textContent=text;}});transcript.append(assistant);}
    else transcript.append(element('p',turn.status==='failed'?'No answer was generated or accepted. Retry requires an explicit action.':'Reviewing the available records…','small'));
   }
   if(visible)transcript.scrollTop=transcript.scrollHeight;
  }
  for(const b of transcript.querySelectorAll('button'))b.disabled=state.busy||locked();
  tick();
 }
 model=modelFactory(render,{...(store?{api:store.transport,managed:true}:api?{api}:{}),locked,onBusy});render(model.state());
 return {show(){visible=true;root.hidden=false;render(model.state());void model.activate();},hide(){visible=false;root.hidden=true;clearTimeout(timer);},clear(){composer.value='';contextUI.clear();model.clear();},busy:model.busy,model,conversations:store,dispose(){clearTimeout(timer);visible=false;model.dispose();store?.dispose();root.replaceChildren();root.hidden=true;}};
}
