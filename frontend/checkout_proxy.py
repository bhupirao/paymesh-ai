"""Public link capability routes only. Never forwards account cookies or bearer tokens."""
import re
TOKEN=r'[A-Za-z0-9_-]{43}'
def checkout_page(path):
 return bool(re.fullmatch('/checkout/'+TOKEN,path))
def allowed_checkout(method,path):
 if len(path)>256:return False
 return bool(re.fullmatch('/api/v1/checkout/'+TOKEN+('(?:/status)?' if method=='GET' else '/pay' if method=='POST' else '(?!)'),path))
