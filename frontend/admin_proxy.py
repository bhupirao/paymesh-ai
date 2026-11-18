"""Exact administrative routes, bounded query values; fixed-target proxy only."""
import re
from urllib.parse import urlsplit, parse_qsl
UUID = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
GETS = frozenset('/api/v1/admin/'+p for p in ('analytics','dashboard','merchants','merchant','payments','refunds','audit','accounts','profile'))
POSTS = frozenset('/api/v1/admin/'+p for p in ('accounts','merchant/approve','merchant/reject','merchant/suspend','merchant/reactivate','profile/password'))
SPA = frozenset('/admin/'+p for p in ('ai','merchants','merchant','pending','payments','refunds','audit','accounts','profile'))

def allowed_admin(method, target):
    if len(target)>2048 or '#' in target or re.search(r'%(?![a-fA-F0-9]{2})',target):return False
    parsed=urlsplit(target)
    if parsed.scheme or parsed.netloc or parsed.fragment:return False
    path=parsed.path
    if method=='POST':return path in POSTS and not parsed.query and '?' not in target
    if method!='GET':return False
    if path not in GETS and not re.fullmatch('/api/v1/admin/(payments|refunds)/'+UUID,path):return False
    try:pairs=parse_qsl(parsed.query,keep_blank_values=True,strict_parsing=True,max_num_fields=10)
    except ValueError:return False
    params=dict(pairs)
    if len(params)!=len(pairs):return False
    if path.endswith('/profile') or re.fullmatch('/api/v1/admin/(payments|refunds)/'+UUID,path):return not params
    keys={'from','to','currency','merchantId'} if path.endswith('/analytics') else {'merchantId'} if path.endswith('/merchant') else {'page','size','search','status','currency','merchantId','sort','from','to'}
    if not params.keys()<=keys:return False
    for key,value in params.items():
        if not value or any(ord(c)<32 or ord(c)==127 for c in value):return False
        if key in ('page','size'):
            if not re.fullmatch(r'[0-9]{1,5}',value) or not (0<=int(value)<=10000 if key=='page' else 1<=int(value)<=100):return False
        elif key=='sort' and value not in ('newest','oldest'):return False
        elif key=='currency' and value not in ('INR','USD'):return False
        elif key=='status' and not re.fullmatch('[A-Z_]{1,24}',value):return False
        elif key in ('merchantId','search') and len(value)>100:return False
        elif key in ('from','to') and (len(value)>35 or not re.fullmatch(r'[0-9TZ:.+\-]+',value)):return False
    return not path.endswith('/merchant') or 'merchantId' in params
