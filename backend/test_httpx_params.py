
import httpx
import inspect

print("httpx version:", httpx.__version__)

# Get the signature of httpx.Client.__init__
sig = inspect.signature(httpx.Client.__init__)
print("\nhttpx.Client.__init__ parameters:")
for param in sig.parameters.values():
    print(f"  {param.name}")

print("\nTrying to create httpx.Client with proxies=None:")
try:
    client = httpx.Client(proxies=None)
    print("Successfully created client with proxies=None!")
    client.close()
except Exception as e:
    print(f"Error: {type(e)} {str(e)}")
    import traceback
    print(traceback.format_exc())
