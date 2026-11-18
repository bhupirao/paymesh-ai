// A tab-history pointer only: never conversation content or credentials.
import { getSession,isUUID } from '../auth/session.js';
const field='paymeshConversation';
export function conversationBookmark(target=globalThis.window){
 const identity=(role,entry)=>{const s=getSession();return s?.sessionId&&s.roles.length===1&&s.roles[0]===role?{subject:s.subject,session:s.sessionId,role,entry}:null;};
 const read=()=>target?.history?.state?.[field];
 function clear(){try{if(read())target.history.replaceState({...target.history.state,[field]:null},'');}catch{}}
 return {clear,save(role,entry,id){const owner=identity(role,entry);if(!owner||!isUUID(id))return;try{target.history.replaceState({...target.history.state,[field]:{...owner,id}},'');}catch{}},load(role,entry){const saved=read(),owner=identity(role,entry);if(!saved)return null;if(!owner||Object.keys(owner).some(k=>saved[k]!==owner[k])||!isUUID(saved.id)){clear();return null;}return saved.id;}};
}
