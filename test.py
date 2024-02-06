import requests, time

print('Testeur papillon-python')
api_url = input('URL de l\'API (http://127.0.0.1:8000) $ ')
if api_url == '':
    api_url = 'http://127.0.0.1:8000'
pronote_url = input('URL de Pronote $ ')
username = input('Nom d\'utilisateur $ ')
password = input('Mot de passe $ ')
ent = input('Code de l\'ENT $ ')

response = requests.post(api_url.rstrip('/') + '/generatetoken', data={'url': pronote_url, 'username': username, 'password': password, 'ent': ent})
print('login effectué')
token = response.json()['token']

start = time.time()
response = requests.get(api_url.rstrip('/') + '/user', params={'token': token})
end = time.time()
print(f'/user ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/timetable', params={'token': token, 'dateString': '2022-01-05'})
end = time.time()
print(f'/timetable ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/homework', params={'token': token, 'dateFrom': '2022-01-05', 'dateTo': '2022-01-09'})
end = time.time()
print(f'/homework ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/grades', params={'token': token})
end = time.time()
print(f'/grades ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/absences', params={'token': token})
end = time.time()
print(f'/absences ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/news', params={'token': token})
end = time.time()
print(f'/news ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/discussions', params={'token': token})
end = time.time()
print(f'/discussions ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')

start = time.time()
response = requests.get(api_url.rstrip('/') + '/export/ical', params={'token': token})
end = time.time()
print(f'/export/ical ({round((end-start)*1000)}ms):')
try:
    print(response.json())
except:
    print('fail')
