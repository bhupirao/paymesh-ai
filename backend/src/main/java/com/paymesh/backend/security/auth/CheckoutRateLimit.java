package com.paymesh.backend.security.auth;
import com.paymesh.backend.security.accounts.AuthStore;
import java.time.Clock;
import java.util.*;
import org.springframework.stereotype.Component;
/** Bounded single-instance abuse control; use a reviewed distributed edge limiter for production. */
@Component
public class CheckoutRateLimit {
 private final Clock clock;private final Map<String,Integer> buckets=new HashMap<>();private long window=-1;
 public CheckoutRateLimit(){this(Clock.systemUTC());} CheckoutRateLimit(Clock clock){this.clock=clock;}
 public synchronized boolean allow(String address,String token,boolean post){long current=clock.millis()/60000;if(current!=window){buckets.clear();window=current;}String kind=post?"P":"G",ip=kind+AuthStore.digest(address),link=kind+AuthStore.digest(token);
  if(buckets.size()>4092)return false;int a=buckets.getOrDefault(ip,0),b=buckets.getOrDefault(link,0);if(a>=(post?20:120)||b>=(post?6:60))return false;buckets.put(ip,a+1);buckets.put(link,b+1);return true;}
}
