"""Exact role-scoped private conversation routes. No arbitrary forwarding."""
import re
from urllib.parse import parse_qsl
ID=r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
def allowed_conversation(method,target):
 if not isinstance(target,str) or len(target)>2048 or '#' in target or re.search(r'%(?![a-fA-F0-9]{2})',target):return False
 parts=target.split('?')
 if len(parts)>2:return False
 base=parts[0];prefix=r'/api/v1/(?:merchant|admin)/ai/conversations'
 if method=='POST':return len(parts)==1 and bool(re.fullmatch(prefix+r'(?:/'+ID+r'/(?:messages|rename|delete))?',base))
 if method!='GET':return False
 is_list=bool(re.fullmatch(prefix,base));is_messages=bool(re.fullmatch(prefix+'/'+ID+'/messages',base))
 if not (is_list or is_messages or re.fullmatch(prefix+r'(?:/'+ID+r'|/creations/'+ID+r'|/'+ID+r'/requests/'+ID+')',base)):return False
 if len(parts)==2 and not parts[1]:return False
 try:pairs=parse_qsl(parts[1] if len(parts)==2 else '',keep_blank_values=True,strict_parsing=True,max_num_fields=4)
 except ValueError:return False
 if len(dict(pairs))!=len(pairs):return False
 keys={'page','size','search','paymentId'} if is_list else {'page','size'} if is_messages else set()
 for key,value in pairs:
  if key not in keys or not value or any(ord(c)<32 or ord(c)==127 for c in value):return False
  if key=='page' and not (re.fullmatch(r'[0-9]{1,5}',value) and int(value)<=10000):return False
  if key=='size' and not (re.fullmatch(r'[0-9]{1,2}',value) and 1<=int(value)<=10):return False
  if key=='search' and len(value)>120:return False
  if key=='paymentId' and not re.fullmatch(ID,value):return False
 return True
