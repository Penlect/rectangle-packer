
import sys
import time
import random
import threading
import subprocess

subprocess.run([sys.executable, 'setup.py', 'develop'], check=True)
subprocess.run([sys.executable, '-m', 'pytest', '-v', '-s'], check=True)


import rpack

random.seed(123)
data = [random.random() for _ in range(10_000)]

def lol():
    t0 = time.time()
    groups = rpack.group(data, 5)
    t1 = time.time()
    print(max(sum(g) for g in groups), t1 - t0)

a = threading.Thread(target=lol)
b = threading.Thread(target=lol)

a.start()
b.start()

a.join()
b.join()

x = 214748364
print(rpack.pack([(x, x), (x, x)]))

