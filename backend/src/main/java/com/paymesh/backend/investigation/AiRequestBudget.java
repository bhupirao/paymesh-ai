package com.paymesh.backend.investigation;
import java.util.concurrent.Semaphore;
import org.springframework.stereotype.Component;
/** One remote AI request at a time across investigation/chat; never queue LLM work. */
@Component public class AiRequestBudget {
 private final Semaphore slot=new Semaphore(1);
 public boolean acquire(){return slot.tryAcquire();}public void release(){slot.release();}
}
