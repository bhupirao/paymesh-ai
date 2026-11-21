// Client-side scheduling, not an HTTP retry or server-limit override.
// Published Java permits 10 auth requests per remote IP in a 60-second bucket.
// Admit at most nine planned operations, then require 61 seconds without auth
// activity (one second covers server epoch-second granularity) before resuming.
export const AUTH_PATHS = new Set(['/api/v1/auth/login','/api/v1/auth/register','/api/v1/auth/refresh','/api/v1/auth/logout','/api/v1/auth/logout-all']);
export class AuthBudget {
  constructor({now=()=>performance.now(),sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}) {
    this.now=now;this.sleep=sleep;this.used=0;this.lastActivity=-Infinity;this.rateLimited=false;this.observationFailed=false;
    this.active=new Map();this.requests=new WeakSet();this.requestCount=0;this.waitCount=0;
  }
  assertHealthy() { if(this.observationFailed)throw new Error('AUTH_OBSERVATION_FAILED');if(this.rateLimited)throw new Error('AUTH_LIMIT_OBSERVED'); }
  request(request,page,pathname) {
    if(request.method()!=='POST'||!AUTH_PATHS.has(pathname))return;
    this.requests.add(request);this.requestCount++;this.lastActivity=this.now();
    const reservation=this.active.get(page);
    if(reservation?.admitted&&!reservation.claimed&&reservation.path===pathname)reservation.claimed=true;
    else this.used++;
  }
  response(request,status) {
    if(!this.requests.has(request))return;
    this.lastActivity=this.now();
    if(status===429)this.rateLimited=true;
  }
  failed(request) { if(this.requests.has(request))this.lastActivity=this.now(); }
  async run(page,pathname,action) {
    if(!AUTH_PATHS.has(pathname)||this.active.has(page))throw new Error('AUTH_ACTION_SCOPE_REQUIRED');
    this.assertHealthy();const began=this.now();
    const reservation={path:pathname,claimed:false,admitted:false};
    this.active.set(page,reservation);
    try {
    while(this.used>=9) {
      this.assertHealthy();
      const remaining=61000-(this.now()-this.lastActivity);
      if(remaining<=0){this.used=0;break;}
      if(this.now()-began+remaining>90000)throw new Error('AUTH_BUDGET_WAIT_LIMIT');
      this.waitCount++;await this.sleep(remaining);
    }
    this.assertHealthy();
    if(this.now()-this.lastActivity>=61000)this.used=0;
    this.used++;this.lastActivity=this.now();
    reservation.admitted=true;
    return await action();
    }finally{this.active.delete(page);}
  }
}
export const authBudget=new AuthBudget();
