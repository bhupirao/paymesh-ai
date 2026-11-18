package com.paymesh.backend.security.accounts;
import com.paymesh.backend.security.accounts.*;
import org.springframework.stereotype.Service;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.annotation.Transactional;
/** Small privacy cleanup batches; no financial/account content is touched. */
@Service
@ConditionalOnProperty(name="paymesh.conversations.cleanup-enabled",havingValue="true",matchIfMissing=true)
public class ConversationRetention {
 private final AuthStore db;private final AccountAdministrationLock lock;
 public ConversationRetention(AuthStore db,AccountAdministrationLock lock){this.db=db;this.lock=lock;}
 @Scheduled(initialDelayString="${paymesh.conversations.cleanup-delay-ms:3600000}",fixedDelayString="${paymesh.conversations.cleanup-delay-ms:3600000}")
 @Transactional(timeout=8)
 public void sweep(){lock.acquire();db.jdbc.update("DELETE FROM "+db.table("ai_conversations")+" WHERE conversation_id IN (SELECT conversation_id FROM "+db.table("ai_conversations")+" WHERE expires_at<=clock_timestamp() ORDER BY expires_at LIMIT 5)");db.jdbc.update("DELETE FROM "+db.table("ai_conversation_creations")+" WHERE (owner_id,portal_role,request_id) IN (SELECT owner_id,portal_role,request_id FROM "+db.table("ai_conversation_creations")+" WHERE expires_at<=clock_timestamp() ORDER BY expires_at LIMIT 50)");}
}
