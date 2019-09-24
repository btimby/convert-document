import os
import sys
import signal
import requests

from multiprocessing import Pool

# signal.signal(signal.SIGINT, signal.SIG_IGN)
url = os.environ.get('UNOSERVICE_URL', 'http://localhost:3000/preview/')


def request(i):
    path = 'sample.odt' if len(sys.argv) < 2 else sys.argv[1]
    data = {'path': path}
    res = requests.get(url, params=data)
    print(i, res.status_code, res.content[:20])


pool = Pool(20)
try:
    pool.map(request, range(10000))

except KeyboardInterrupt:
    pool.terminate()
    pool.join()
