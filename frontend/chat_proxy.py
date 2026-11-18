"""Only authenticated Java chat adapters, never Python/LLM or arbitrary paths."""
import re
ID=r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
def allowed_chat(method,path):
 return method=='POST' and len(path)<200 and bool(re.fullmatch(r'/api/v1/(?:merchant/ai/chat|admin/ai/chat|payments/'+ID+r'/ai/chat)',path))
