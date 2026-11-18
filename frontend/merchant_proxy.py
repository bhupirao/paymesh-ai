"""Narrow Merchant portal routes. Ownership is derived only by Java."""
from urllib.parse import urlsplit,parse_qsl
from admin_proxy import allowed_admin, UUID
import re
SPA=frozenset('/merchant/'+p for p in ('ai','payments','refunds','profile','security','payment-links','payment-links/create'))
def allowed_merchant(method,target):
    if any(ord(c)<32 or ord(c)==127 for c in target):return False
    parsed=urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment or not target.startswith('/api/v1/merchant/'):return False
    base=parsed.path.removeprefix('/api/v1/merchant/')
    if base=='payment-links' or re.fullmatch('payment-links/'+UUID+'(?:/cancel)?',base):
        if len(target)>2048 or '#' in target or re.search(r'%(?![a-fA-F0-9]{2})',target):return False
        if method=='POST':return not parsed.query and '?' not in target and (base=='payment-links' or base.endswith('/cancel'))
        if method!='GET' or base.endswith('/cancel'):return False
        if base!='payment-links':return not parsed.query and '?' not in target
        try:pairs=parse_qsl(parsed.query,keep_blank_values=True,strict_parsing=True,max_num_fields=5)
        except ValueError:return False
        if len(dict(pairs))!=len(pairs):return False
        for k,v in pairs:
            if k not in ('page','size','search','status','currency') or not v or any(ord(c)<32 or ord(c)==127 for c in v):return False
            if k=='page' and (not re.fullmatch('[0-9]{1,5}',v) or int(v)>10000):return False
            if k=='size' and (not re.fullmatch('[0-9]{1,2}',v) or not 1<=int(v)<=50):return False
            if k=='search' and len(v)>100:return False
            if k=='status' and v not in ('ACTIVE','EXPIRED','CANCELLED','PAID','PROCESSING'):return False
            if k=='currency' and v not in ('INR','USD'):return False
        return True
    if method=='POST':return target=='/api/v1/merchant/profile/password'
    if method!='GET' or base not in ('analytics','dashboard','payments','refunds','profile'):return False
    if not allowed_admin('GET',target.replace('/api/v1/merchant/','/api/v1/admin/',1)):return False
    try:keys={k for k,v in parse_qsl(parsed.query,strict_parsing=True)}
    except ValueError:return False
    allowed={'currency','from','to'} if base in ('dashboard','analytics') else set() if base=='profile' else {'page','size','search','status','currency','sort','from','to'}
    return keys<=allowed
