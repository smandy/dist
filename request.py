# http://docs.python-requests.org/en/v0.10.7/user/quickstart/#custom-headers

import requests
import json

url = 'http://localhost:8888/jobs/add'
payload = {'some': 'data', 'woot' : [1,2,3] }
headers = {'content-type': 'application/json'}
r = requests.post(url, data=json.dumps(payload), headers=headers)
print r
