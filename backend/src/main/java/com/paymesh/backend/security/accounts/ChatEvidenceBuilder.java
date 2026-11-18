package com.paymesh.backend.security.accounts;
import com.paymesh.backend.chat.*;
import com.paymesh.backend.security.business.BusinessAccess;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.*;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.oauth2.jwt.JwtDecoder;

/** Short authorization transaction surrounds a separate repeatable-read projection, never HTTP. */
@Service
public class ChatEvidenceBuilder {
 private final AccountAdministrationLock lock;private final MerchantPortal merchant;private final MerchantAdministration admin;private final BusinessAccess business;private final AuthStore db;private final JwtDecoder decoder;private final ChatProjectionQueries projection;
 public ChatEvidenceBuilder(AccountAdministrationLock lock,MerchantPortal merchant,MerchantAdministration admin,BusinessAccess business,AuthStore db,JwtDecoder decoder,ChatProjectionQueries projection){this.lock=lock;this.merchant=merchant;this.admin=admin;this.business=business;this.db=db;this.decoder=decoder;this.projection=projection;}
 public record Selection(UUID actor,long version,String jti,String endpoint,String merchantId,UUID paymentId,UUID linkId,ChatDtos.Statistics statistics,boolean isAdmin){}
 public record Snapshot(ObjectNode request,Map<String,ChatDtos.Reference> references,List<String> limitations,Map<String,Object> range,Selection selection){@Override public String toString(){return "Authorized chat snapshot [redacted]";}}
 private Selection authorize(String endpoint,UUID path,ChatDtos.Input input){
  lock.acquire();var auth=SecurityContextHolder.getContext().getAuthentication();if(!(auth instanceof JwtAuthenticationToken token))throw new ChatFailure(401,"AUTHENTICATION_REQUIRED","Sign in again.");
  try{decoder.decode(token.getToken().getTokenValue());}catch(org.springframework.security.oauth2.jwt.JwtException ex){throw new ChatFailure(401,"AUTHENTICATION_REQUIRED","Current authorization is no longer valid.");}
  var actor=business.actor();boolean isAdmin=actor.admin();String owner="";
  if(endpoint.equals("merchant")||!isAdmin){var scope=merchant.scope();owner=scope.merchantId();isAdmin=false;}else admin.actor();
  if(endpoint.equals("admin")&&!isAdmin)throw new AccountAccessDeniedException();
  var c=input.context();if(!isAdmin&&c!=null&&c.merchantId()!=null)throw ChatDtos.invalid();
  if(path!=null&&c!=null&&(c.paymentId()!=null||c.paymentLinkId()!=null))throw ChatDtos.invalid();
  UUID payment=path!=null?path:c!=null&&c.paymentId()!=null?ChatDtos.uuid(c.paymentId()):null,link=c!=null&&c.paymentLinkId()!=null?ChatDtos.uuid(c.paymentLinkId()):null;
  if(isAdmin&&c!=null&&c.merchantId()!=null){owner=c.merchantId();if(db.jdbc.queryForObject("SELECT count(*) FROM "+db.table("merchants")+" WHERE merchant_id=?",Integer.class,owner)!=1)throw missing();}
  if(link!=null){var rows=db.jdbc.queryForList("SELECT merchant_id FROM "+db.table("payment_links")+" WHERE link_id=? AND (?='' OR merchant_id=?)",link,owner,owner);if(rows.isEmpty())throw missing();String linkOwner=rows.getFirst().get("merchant_id").toString();if(!isAdmin&&!owner.equals(linkOwner))throw missing();
   // Only the link-selected current attempt/success, never a token or client-supplied payment.
   var candidates=db.jdbc.queryForList("SELECT payment_id FROM "+db.table("checkout_attempts")+" WHERE link_id=? ORDER BY CASE WHEN status='FAILED' THEN 1 ELSE 0 END,created_at DESC,attempt_id DESC LIMIT 1",link);if(!candidates.isEmpty())payment=(UUID)candidates.getFirst().get("payment_id");owner=linkOwner;
  }
  if(payment!=null){var p=business.payment(actor,payment,false);if(!owner.isEmpty()&&!owner.equals(p.getMerchantId()))throw missing();owner=p.getMerchantId();}
  return new Selection(actor.id(),actor.version(),token.getToken().getId(),endpoint,owner,payment,link,c==null?null:c.statistics(),isAdmin);
 }
 @Transactional(propagation=Propagation.MANDATORY)
 public Selection withinTransaction(String endpoint,ChatDtos.Input input){return authorize(endpoint,null,input);}
 @Transactional(readOnly=true,propagation=Propagation.REQUIRES_NEW,isolation=Isolation.READ_COMMITTED,timeout=8)
 public Snapshot collect(String endpoint,UUID payment,ChatDtos.Input input,UUID correlation){return projection.build(authorize(endpoint,payment,input),input,correlation);}
 @Transactional(readOnly=true,propagation=Propagation.REQUIRES_NEW,isolation=Isolation.READ_COMMITTED,timeout=5)
 public void recheck(Snapshot snapshot,ChatDtos.Input input,UUID path){var now=authorize(snapshot.selection().endpoint(),path,input);var before=snapshot.selection();if(!now.actor().equals(before.actor())||now.version()!=before.version()||!Objects.equals(now.jti(),before.jti())||now.isAdmin()!=before.isAdmin()||!now.merchantId().equals(before.merchantId()))throw new AccountAccessDeniedException();
  // A link may acquire a new financial attempt during inference; reauthorize the original
  // detached payment too. The explanation remains an explicitly dated historical snapshot.
  if(before.paymentId()!=null)business.payment(business.actor(),before.paymentId(),false);
 }
 private ChatFailure missing(){return new ChatFailure(404,"CONTEXT_UNAVAILABLE","Selected context is unavailable.");}
}
