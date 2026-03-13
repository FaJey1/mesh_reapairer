import logging
import time

def measure_time(func, *args, **kwargs):
    start = time.time()
    result = func(*args, **kwargs)
    return result, time.time() - start
