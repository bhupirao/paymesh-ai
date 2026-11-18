package com.paymesh.backend.service.impl;
import com.paymesh.backend.security.accounts.CheckoutTransactions;
import java.util.Map;
import org.springframework.stereotype.Service;
/** Acceptance is REQUIRES_NEW; this coordinator deliberately has no transaction. */
@Service
public class CheckoutExecution {
 private final CheckoutTransactions transactions;private final AcceptedPaymentExecution orchestration;
 public CheckoutExecution(CheckoutTransactions transactions,AcceptedPaymentExecution orchestration){this.transactions=transactions;this.orchestration=orchestration;}
 public Map<String,Object> pay(String token,String key,String simulation){var accepted=transactions.accept(token,key,simulation);if(!accepted.replay()){
  try{var payment=orchestration.execute(accepted.payment(),accepted.simulation());if(payment.status().equals("PROCESSING"))transactions.uncertain(accepted.attemptId());}
  catch(RuntimeException ex){transactions.uncertain(accepted.attemptId());}
 }return transactions.read(token);}
}
