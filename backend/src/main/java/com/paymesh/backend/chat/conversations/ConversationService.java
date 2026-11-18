package com.paymesh.backend.chat.conversations;
import com.paymesh.backend.chat.*;
import com.paymesh.backend.investigation.AiRequestBudget;
import com.paymesh.backend.security.accounts.ChatEvidenceBuilder;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;
@Service
public class ConversationService {
 private final ConversationTransactions store;private final ChatEvidenceBuilder evidence;private final AiChatClient python;private final AiRequestBudget budget;
 public ConversationService(ConversationTransactions store,ChatEvidenceBuilder evidence,AiChatClient python,AiRequestBudget budget){this.store=store;this.evidence=evidence;this.python=python;this.budget=budget;}
 @Transactional(propagation=Propagation.NEVER)
 public Map<String,Object> send(String portal,UUID id,ConversationDtos.Send input){var work=store.begin(portal,id,input);if(work.immediate()!=null)return work.immediate();boolean acquired=false;
  try{var snapshot=evidence.collect(portal,null,work.input(),UUID.randomUUID());if(!snapshot.selection().actor().equals(work.actor())||snapshot.selection().version()!=work.authorizationVersion()||!snapshot.selection().merchantId().equals(work.merchantId()))throw new ChatFailure(403,"ACCESS_DENIED","Conversation scope changed before inference.");ChatRules.expected(snapshot.request());if(!budget.acquire())throw new ChatFailure(503,"AI_CAPACITY","AI capacity is busy. Reconcile and retry only deliberately.");acquired=true;var result=ChatResponseValidator.validate(python.chat(snapshot.request()),snapshot);evidence.recheck(snapshot,work.input(),null);return store.finish(portal,work,result);
  }catch(RuntimeException e){try{store.fail(portal,work,e instanceof ChatFailure f?f.code():"REQUEST_FAILED");}catch(RuntimeException ignored){/* Commit/auth/deletion may be uncertain. Never print content or claim rollback success. */}throw e;}
  finally{if(acquired)budget.release();}
 }
}
