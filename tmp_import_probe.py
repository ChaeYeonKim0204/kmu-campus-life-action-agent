import time

print("before app import", flush=True)
t = time.time()
import app  # noqa: F401
print(f"after app import {time.time() - t:.2f}s", flush=True)
