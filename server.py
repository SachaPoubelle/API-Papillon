# importe les modules importants
from pyexpat.errors import messages
from os import environ
import pronotepy
import datetime
import time
import secrets
import json
import socket
import base64
import pickle
from sanic import Sanic
from sanic.response import json as rjson
from sanic.response import text
from sanic.exceptions import ServerError, NotFound, BadRequest, Forbidden


import sentry_sdk
from sentry_sdk.scrubber import EventScrubber, DEFAULT_DENYLIST 

import resource
resource.setrlimit(resource.RLIMIT_CORE, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))

# importe les ENT
from pronotepy.ent import *

API_VERSION = open('VERSION', 'r').read().strip()
MAINTENANCE = json.load(open('maintenance.json', 'r', encoding='utf8'))
CAS_LIST = json.load(open('cas_list.json', 'r', encoding='utf8'))

denylist = DEFAULT_DENYLIST + [
	"token"
	"qrToken",
	"checkCode",
	"uuid",
	"password",
	"login",
] 

try :
	sentry_sdk.init(
		dsn=environ['DSN_URL'],
		release=API_VERSION,
		send_default_pii=True,
		event_scrubber=EventScrubber(denylist=denylist),
	)
except Exception as e:
	print("WARN: Couldn't init Sentry")
	print(e)

app = Sanic("PapillonRest")

app.config.REQUEST_TIMEOUT = 5
app.config.RESPONSE_TIMEOUT = 5

app.update_config({
	'REQUEST_TIMEOUT': 5,
	'RESPONSE_TIMEOUT': 5,
})

@app.middleware('response')
async def CORS(request, response):
	response.headers['Access-Control-Allow-Origin'] = '*'
	response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
	response.headers['Access-Control-Allow-Headers'] = 'Authorization,Keep-Alive,User-Agent,If-Modified-Since,Cache-Control,Content-Type'
	response.headers['Access-Control-Expose-Headers'] = 'Authorization,Keep-Alive,User-Agent,If-Modified-Since,Cache-Control,Content-Type'
	if request.method == 'OPTIONS':
		response.headers['Access-Control-Max-Age'] = 1728000
		response.headers['Content-Type'] = 'text/plain charset=UTF-8'
		response.headers['Content-Length'] = 0
		response.status = 204

# système de tokens
@app.before_server_start
async def attach_saved_clients(app, loop):
    app.ctx.saved_clients = {}

"""
saved_clients ->
	token ->
		client -> instance de pronotepy.Client
		last_interaction -> int (provenant de time.time(), entier représentant le temps depuis la dernière intéraction avec le client)
"""


client_timeout_threshold = 300 # le temps en sec avant qu'un jeton ne soit rendu invalide

def get_client(token) -> tuple[str, pronotepy.Client|None]:
	"""Retourne le client Pronote associé au jeton.

	Args:
		token (str): le jeton à partir duquel retrouver le client.
		instance (bool): si True, le client ne sera pas recherché sur les autres instances.

	Returns:
		tuple: le couple (statut, client?) associé au jeton
			str: le statut de la demande ('ok' si le client est trouvé, 'expired' si le jeton a expiré, 'notfound' si le jeton n'est pas associé à un client)
			pronotepy.Client|None: une instance de client si le token est valide, None sinon.

	"""
	print(len(app.ctx.saved_clients), 'valid tokens')

	if MAINTENANCE['enable']:
		return 'maintenance', None
	if token in app.ctx.saved_clients:
		client_dict = app.ctx.saved_clients[token]
		if time.time() - client_dict['last_interaction'] < client_timeout_threshold:
			client_dict['last_interaction'] = time.time()
			return 'ok', client_dict['client']
		else:
			del app.ctx.saved_clients[token]
			return 'expired', None
	else:
		return 'notfound', None

@app.get('/')
async def home(request):
	return rjson({
		'status': 'ok',
		'message': 'server is running',
		'server': socket.gethostname(),
		'version': API_VERSION,
		'ent_list': CAS_LIST if not MAINTENANCE['enable'] else []
	})

@app.get('/infos')
async def infos(request):
	return rjson({
		'status': 'ok',
		'message': 'server is running',
		'server': socket.gethostname(),
		'version': API_VERSION,
		'ent_list': CAS_LIST if not MAINTENANCE['enable'] else []
	})
 
# requête initiale :
# un client doit faire
# token = POST /generatetoken body={url, username, password, ent}
# GET * token=token
@app.route('/generatetoken', methods=['POST'])
async def generate_token(request):
	body = request.form

	if not body is None:
		## version is an URL parameter
		version = request.args.get('version', '2')
		type = request.args.get('type', 'eleve')
		method = request.args.get('method', 'url')

		noENT = False
		  
		# if no version in URL
		if version == '2':
			try :
				body['url'] = base64.b64decode(body['url'][0]).decode('utf-8')
				body['username'] = base64.b64decode(body['username'][0]).decode('utf-8')
				body['password'] = base64.b64decode(body['password'][0]).decode('utf-8')
				if 'ent' in body:
					body['ent'] = base64.b64decode(body['ent'][0]).decode('utf-8')
			except Exception as e:
				return rjson({
					"token": False,
					"error": 'Invalid base64'
				}, status=400)
		else :
			try :
				body['url'] = body['url'][0]
				body['username'] = body['username'][0]
				body['password'] = body['password'][0]
				if 'ent' in body:
					body['ent'] = body['ent'][0]
			except Exception as e:
				return rjson({
					"token": False,
					"error": 'Invalid plain text'
				}, status=400)

		if method == "url":
			for rk in ('url', 'username', 'password', 'ent'):
				if not rk in body and rk != 'ent':
					return rjson({
						"token": False,
						"error": f'Missing {rk}'
					}, status=400)
				
				elif not rk in body and rk == 'ent':
					noENT = True 

			try:
				if noENT:
					if type == 'parent':
						client = pronotepy.ParentClient(body['url'], username=body['username'], password=body['password'])
					else:
						client = pronotepy.Client(body['url'], username=body['username'], password=body['password'])
				else:
					if type == 'parent':
						client = pronotepy.ParentClient(body['url'], username=body['username'], password=body['password'], ent=getattr(pronotepy.ent, body['ent']))
					else:
						client = pronotepy.Client(body['url'], username=body['username'], password=body['password'], ent=getattr(pronotepy.ent, body['ent']))
			except Exception as e:
				print(f"Error while trying to connect to {body['url']}")
				return rjson({
					"token": False,
					"error": str(e),
				}, status=498)

		elif method == "qrcode":
			for rk in ('url', 'qrToken', 'login', 'checkCode', 'uuid'):
				if not rk in body:
					return rjson({
						"token": False,
						"error": f'Missing {rk}'
					},status=400)
				elif rk == "checkCode":
					if len(body["checkCode"]) != 4:
						return rjson({
							"token": False,
							"error": f'checkCode must be 4 characters long (got {len(body["checkCode"])})'
						},status=400)

			try:
				client = pronotepy.Client.qrcode_login({
					"jeton": body['qrToken'],
					"login": body['login'],
					"url": body['url']
				}, body['checkCode'], body['uuid'])
			except Exception as e:         
				return rjson({
					"token": False,
					"error": str(e),
				}, status=400)
		
		elif method == "token":
			for rk in ('url', 'username', 'password', 'uuid'):
				if not rk in body:
					return rjson({
						"token": False,
						"error": f'Missing {rk}'
					}, status=400)

			try:
				client = pronotepy.Client.token_login(
					pronote_url = body['url'],
					username = body['username'],
					password = body['password'],
					uuid=body['uuid']
				)
			except Exception as e:
				print(f"Error while trying to connect to {body['url']}")

				return rjson({
					"token": False,
					"error": str(e),
				}, status=498)

		token = secrets.token_urlsafe(16)
		# Set current period
		client.calculated_period = __get_current_period(client)
		client.activated_period = __get_current_period(client, False, None, True)

		client_pickle = base64.b64encode(pickle.dumps(client)).decode()

		app.ctx.saved_clients[token] = {
			'client': client,
			'last_interaction': time.time()
		}



		#print(len(app.ctx.saved_clients), 'valid tokens')

		# if error return error
		if client.logged_in:
			if method != "url":
				QRtokenArray = {
					"token": token,
					"error": False,
					"qr_credentials": {
						"username": client.username,
						"password": client.password,
						"url": client.pronote_url
					}
				}

				return QRtokenArray

			return rjson({
				"token": token,
				"error": False
			})
		else:
			return rjson({
				"token": False,
				"error": "Login failed",
			}, status=498)
	else:
		return rjson({
			"token": False,
			"error": "missingbody",
		}, 400)


# TODO: METTRE A JOUR CETTE PARTIE SI DES PROBLEMES APPARAISSENT
# Peut poser problème avec certains établissements
def __get_current_period(client: pronotepy.Client, wantSpecificPeriod: bool = False, specificPeriod: str = None, wantAllPeriods: bool = False) -> pronotepy.Period:
	"""
	Permet de récupérer la période actuelle du client Pronote ou une période spécifique.
	
	Args:
		client (pronotepy.Client): Le client Pronote
		wantSpecificPeriod (bool, optional): Si True, la fonction va retourner la période spécifiée par specificPeriod. Si False, la fonction va retourner la période actuelle. Defaults to False.
		specificPeriod (str, optional): La période à retourner. Defaults to None.
		wantAllPeriods (bool, optional): Si True, la fonction va retourner toutes les périodes. Defaults to False.
		
	Returns:
		pronotepy.Period: La période actuelle ou la période spécifiée.
	"""
	
	if client.logged_in:
		if not wantSpecificPeriod:
			CURRENT_PERIOD_NAME = client.current_period.name.split(' ')[0]
			if CURRENT_PERIOD_NAME == 'Trimestre':
				CURRENT_PERIOD_NAME = 'Trimestre'
			elif CURRENT_PERIOD_NAME == 'Semestre':
				CURRENT_PERIOD_NAME = 'Semestre'
			elif CURRENT_PERIOD_NAME == 'Année':
				CURRENT_PERIOD_NAME = 'Année'
			else:
				return client.current_period
			
			allPeriods = []
			currentPeriods = []

			for period in client.periods:
				if period.name.split(' ')[0] == CURRENT_PERIOD_NAME:
					currentPeriods.append(period)

			for i in range(len(currentPeriods)):
				period = currentPeriods[i]
				if not wantAllPeriods:   
					raw = datetime.datetime.now().date()
					now = datetime.datetime(raw.year, raw.month, raw.day)

					if period.start <= now <= period.end:
						return period

					if i == len(currentPeriods) - 1:
						return period
				else:
					allPeriods.append(period)
			
			return allPeriods
		else:
			for period in client.periods:
				if period.name == specificPeriod:
					return period
			return __get_current_period(client, False, None)


@app.route('/changePeriod', methods=['POST'])
async def change_period(request):
	"""
	Permets de changer la période actuelle du client Pronote.
	
	Args:
		token (str): Le token du client Pronote
		periodName (str): Le nom de la période à sélectionner
		
	Returns:
		dict[str, str]: Le statut de la requête et le nom de la période sélectionnée
	"""
	
	token = request.args.get('token')
	periodName = request.args.get('periodName')

	success, client = get_client(token)
	if success == 'ok':
		if client.logged_in:
			try:
				client.calculated_period = __get_current_period(client, True, periodName)
				return rjson({
					'status': 'ok',
					'period': client.calculated_period.name
				})
			except Exception as e:
				return text('"'+success+'"', status=498)
	else:
		return text('"'+success+'"', status=498)


@app.route('/user', methods=['GET'])
async def user(request):
	"""
	Récupère les informations de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		dict: Les informations de l'utilisateur sous la forme : 
		
		{ 
			"name": str,
			"class": str, 
			"establishment": str, 
			"phone": str,
			"address": list[str], 
			"email": str,
			"ine": str,
			"profile_picture": str|None, 
			"delegue": bool, 
			"periodes": list[dict] 
		}
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		if client.logged_in:
			periods = []
			for period in client.periods:
				periods.append({
					'start': period.start.strftime('%Y-%m-%d'),
					'end': period.end.strftime('%Y-%m-%d'),
					'name': period.name,
					'id': period.id,
					'actual': client.calculated_period.id == period.id
				})

			etabData = ""
			try:
				etabData = client.info.establishment
			except Exception as err:
				etabData = ""

			phone = ""
			try:
				phone = client.info.phone
			except Exception as err:
				phone = ""

			email = ""
			try:
				email = client.info.email
			except Exception as err:
				email = ""

			address = []
			try:
				address = client.info.address
			except Exception as err:
				address = []

			ine_number = ""
			try:
				ine_number = client.info.ine_number
			except Exception as err:
				ine_number = ""

			usertype = type(client).__name__

			children = []
			if (usertype == "ParentClient"):
				try:
					children = client.children.to_dict()
				except Exception as err:
					children = []

			userData = {
				"name": client.info.name,
				"class": client.info.class_name,
				"establishment": etabData,
				"phone": phone,
				"email": email,
				"address": address,
				"ine": ine_number,
				"profile_picture": client.info.profile_picture.url if client.info.profile_picture else None,
				"delegue": client.info.delegue,
				"periods": periods,
				"client": {
					"type": usertype,
					"children": children
				}
			}

			return rjson(userData)
	else:
		return text('"'+success+'"', status=498)


@app.route('/timetable', methods=['GET'])
async def timetable(request):
	"""
	Récupère l'emploi du temps de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		dateString (str): La date à récupérer sous la forme YYYY-MM-DD
		
	Returns:
		list[dict]: Les informations de l'emploi du temps :
		
		[{
			"id": str,
			"num": int,
			"subject": {
				"id": str,
				"name": str,
				"groups": bool
			},
			"teachers": list[str],
			"rooms": list[str],
			"group_names": list[str]
			"start": str,
			"end": str,
			"duration": int
			"is_cancelled": bool,
			"is_outing": bool,
			"is_detention": bool,
			"is_exempted": bool,
			"is_test": bool,
		}]
	"""
	
	token = request.args.get('token')
	dateString = request.args.get('dateString')

	dateToGet = None

	try :
		dateToGet = datetime.datetime.strptime(dateString, "%Y-%m-%d").date()
	except Exception as e:
		dateToGet = datetime.datetime.now().date()
	success, client = get_client(token)

	if success == 'ok':
		if client.logged_in:
			lessons = []
			try :
				lessons = client.lessons(dateToGet)
			except Exception as e:
				lessons = []

			lessonsData = []
			for lesson in lessons:
				files = []
				lessonContent = []

				try :
					if lesson.content != None:
						for file in lesson.content.files:
							files.append({
								"id": file.id,
								"name": file.name,
								"url": file.url,
								"type": file.type
							})

						lessonContent = {
							"title": lesson.content.title,
							"description": lesson.content.description,
							"category": lesson.content.category,
							"files": files
						}
				except Exception as e:
					lessonContent = []

				lessonData = {
					"id": lesson.id,
					"num": lesson.num,
					"subject": {
						"id": lesson.subject.id if lesson.subject is not None else "0",
						"name": lesson.subject.name if lesson.subject is not None else "",
						"groups": lesson.subject.groups if lesson.subject is not None else False
					},
					"teachers": lesson.teacher_names,
					"rooms": lesson.classrooms,
					"group_names": lesson.group_names,
					"memo": lesson.memo,
					"content": lessonContent,
					"virtual": lesson.virtual_classrooms,
					"start": lesson.start.strftime("%Y-%m-%d %H:%M"),
					"end": lesson.end.strftime("%Y-%m-%d %H:%M"),
					"background_color": lesson.background_color,
					"status": lesson.status,
					"is_cancelled": lesson.canceled,
					"is_outing": lesson.outing,
					"is_detention": lesson.detention,
					"is_exempted": lesson.exempted,
					"is_test": lesson.test,
				}
				lessonsData.append(lessonData)

			return rjson(lessonsData)
	else:
		return text('"'+success+'"', status=498)

@app.route('/content', methods=['GET'])
async def content(request):
	"""
	Récupère le contenu des cours.
	
	Args:
		token (str): Le token du client Pronote
		dateString (str): La date à récupérer sous la forme YYYY-MM-DD
		
	Returns:
		list[dict]: Les contenus du cours 
	"""
	
	token = request.args.get('token')
	dateString = request.args.get('dateString')

	dateToGet = datetime.datetime.strptime(dateString, "%Y-%m-%d").date()
	success, client = get_client(token)

	if success == 'ok':
		if client.logged_in:
			content = client.lessons(dateToGet, dateToGet)

			contentData = []
			for lesson in content:
				if lesson.content != None:
					for contentElement in lesson.content:
						files = []
						for file in contentElement.files:
							files.append({
								"id": file.id,
								"name": file.name,
								"url": file.url,
								"type": file.type
							})
						
						contentList = {
							"title": contentElement.title,
							"description": contentElement.description,
							"category": contentElement.category,
							"files": files
						}

				contentData.append(contentList)

			return rjson(contentData)
	else:
		return text('"'+success+'"', status=498)

@app.route('/homework', methods=['GET'])
async def homework(request):
	"""
	Récupère les devoirs de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		dateFrom (str): La date de début à récupérer sous la forme YYYY-MM-DD
		dateTo (str): La date de fin à récupérer sous la forme YYYY-MM-DD
		
	Returns:
		list[dict]: Les informations des devoirs
	"""
	
	token = request.args.get('token')
	dateFrom = request.args.get('dateFrom')
	dateTo = request.args.get('dateTo')

	try :
		dateFrom = datetime.datetime.strptime(dateFrom, "%Y-%m-%d").date()
		dateTo = datetime.datetime.strptime(dateTo, "%Y-%m-%d").date()
	except Exception as e:
		dateFrom = datetime.datetime.now().date()
		dateTo = datetime.datetime.now().date()
	success, client = get_client(token)

	if success == 'ok':
		if client.logged_in:
			homeworks = client.homework(date_from=dateFrom, date_to=dateTo)

			homeworksData = []
			for homework in homeworks:
				files = []
				for file in homework.files:
					files.append({
						"id": file.id,
						"name": file.name,
						"url": file.url,
						"type": file.type
					})

				local_id = ""

				# return a combination of the 20 first letters of description, 2 first letters of subject name and the date
				if len(homework.description) > 20:
					local_id += homework.description[:20]
				else:
					local_id += homework.description
				
				local_id += homework.subject.name[:2]
				local_id += homework.date.strftime("%Y-%m-%d_%H:%M")

				homeworkData = {
					"id": homework.id,
					"local_id": local_id,
					"subject": {
						"id": homework.subject.id,
						"name": homework.subject.name,
						"groups": homework.subject.groups,
					},
					"description": homework.description,
					"background_color": homework.background_color,
					"done": homework.done,
					"date": homework.date.strftime("%Y-%m-%d %H:%M"),
					"files": files
				}
				homeworksData.append(homeworkData)

			return rjson(homeworksData)
	else:
		return text('"'+success+'"', status=498)


def __get_grade_state(grade_value, significant:bool = False) -> int|str :
	"""
	Récupère l'état d'une note sous forme d'int. (Non Rendu, Absent, etc.)
	
	Args:
		grade_value (str): La valeur de la note
		significant (bool): Si on souhaite récupérer l'état de la note ou la note elle-même. Si True on récupère l'état sous la forme d'un int :
			1 : Absent
			2 : Dispensé
			3 : Non Noté
			4 : Inapte
			5 : Non Rendu
			6 : Absent compte 0
			7 : Non Rendu compte 0
			8 : Félicitations
			Si False on récupère la note elle-même ou -1 si la note ne compte pas comme telle. Defaults to False.
		
	Returns:
		int|str: L'état de la note sous forme d'int ou la note elle-même (str) si significant est False.    
	"""
	
	grade_value = str(grade_value)

	if significant:
		grade_translate = [
			"Absent",
			"Dispense",
			"NonNote",
			"Inapte",
			"NonRendu",
			"AbsentZero",
			"NonRenduZero",
			"Felicitations"
		]
		try:
			int(grade_value[0])
			return 0
		except (ValueError, IndexError):
			if grade_value == "":
				return -1
			return grade_translate.index(grade_value) + 1
	else:
		try:
			int(grade_value[0])
			return grade_value
		except (ValueError, IndexError):
			return "-1"


def __transform_to_number(value)->float|int:
	"""
	Transforme une valeur en nombre (int ou float)
	
	Args:
		value (str): La valeur à transformer
		
	Returns:
		float|int: La valeur transformée ('1,5' -> 1.5)
	"""
	
	try:
		return int(value)
	except ValueError:
		return float(value.replace(",", "."))


@app.route('/grades', methods=['GET'])
async def grades(request):
	"""
	Récupère les notes de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		dict: Les informations des notes
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		allGrades = []
		try :
			allGrades = client.calculated_period.grades
		except Exception as e:
			allGrades = []
		gradesData = []
		for grade in allGrades:
			gradeData = {
				"id": grade.id,
				"subject": {
					"id": grade.subject.id,
					"name": grade.subject.name,
					"groups": grade.subject.groups,
				},
				"date": grade.date.strftime("%Y-%m-%d %H:%M"),
				"description": grade.comment,
				"is_bonus": grade.is_bonus,
				"is_optional": grade.is_optionnal,
				"is_out_of_20": grade.is_out_of_20,
				"grade": {
					"value": __transform_to_number(__get_grade_state(grade.grade)),
					"out_of": __transform_to_number(grade.out_of),
					"coefficient": __transform_to_number(grade.coefficient),
					"average": __transform_to_number(__get_grade_state(grade.average)),
					"max": __transform_to_number(__get_grade_state(grade.max)),
					"min": __transform_to_number(__get_grade_state(grade.min)),
					"significant": __get_grade_state(grade.grade, True),
				}
			}

			gradesData.append(gradeData)

		averagesData = []

		allAverages = client.calculated_period.averages
		for average in allAverages:
			averageData = {
				"subject": {
					"id": average.subject.id,
					"name": average.subject.name,
					"groups": average.subject.groups,
				},
				"average": __transform_to_number(__get_grade_state(average.student)),
				"class_average": __transform_to_number(__get_grade_state(average.class_average)),
				"max": __transform_to_number(__get_grade_state(average.max)),
				"min": __transform_to_number(__get_grade_state(average.min)),
				"out_of": __transform_to_number(__get_grade_state(average.out_of)),
				"significant": __get_grade_state(average.student, True),
				"color": average.background_color if average.background_color != None else "#08BE88"
			}

			averagesData.append(averageData)

		gradeReturn = {
			"grades": gradesData,
			"averages": averagesData,
			"overall_average": __transform_to_number(__get_grade_state(client.calculated_period.overall_average)),
			"class_overall_average": __transform_to_number(__get_grade_state(client.calculated_period.class_overall_average)),
		}

		return rjson(gradeReturn)
	else:
		return text('"'+success+'"', status=498)

@app.route('/absences', methods=['GET'])
async def absences(request):
	"""
	Récupère les absences de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		allPeriods (bool): Si toutes les périodes doivent être récupérées. Par défaut, toutes les périodes sont récupérées.
		
	Returns:
		list[dict]: Les informations des absences
	"""
	
	token = request.args.get('token')
	allPeriods = request.args.get('allPeriods', default=True)

	success, client = get_client(token)
	if success == 'ok':
		if allPeriods:
			allAbsences = [absence for period in client.activated_period for absence in period.absences]
		else:
			allAbsences = client.calculated_period.absences

		absencesData = []
		for absence in allAbsences:
			absenceData = {
				"id": absence.id,
				"from": absence.from_date.strftime("%Y-%m-%d %H:%M"),
				"to": absence.to_date.strftime("%Y-%m-%d %H:%M"),
				"justified": absence.justified,
				"hours": absence.hours,
				"reasons": absence.reasons,
			}

			absencesData.append(absenceData)

		return rjson(absencesData)
	else:
		return text('"'+success+'"', status=498)


@app.route('/delays', methods=['GET'])
async def delays(request):
	"""
	Récupère les retards de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		allPeriods (bool): Si toutes les périodes doivent être récupérées. Par défaut, toutes les périodes sont récupérées.
		
	Returns:
		list[dict]: Les informations des retards
	"""
	
	token = request.args.get('token')
	allPeriods = request.args.get('allPeriods', default=True)

	success, client = get_client(token)
	if success == 'ok':
		if allPeriods:
			allDelays = [delay for period in client.activated_period for delay in period.delays]
		else:
			allDelays = client.calculated_period.delays

		delaysData = []
		for delay in allDelays:
			delayData = {
				"id": delay.id,
				"date": delay.date.strftime("%Y-%m-%d %H:%M"),
				"duration": delay.minutes,
				"justified": delay.justified,
				"justification": delay.justification,
				"reasons": delay.reasons,
			}

			delaysData.append(delayData)

		return rjson(delaysData)
	else:
		return text('"'+success+'"', status=498)


@app.route('/punishments', methods=['GET'])
async def punishments(request):
	"""
	Récupère les punitions de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		allPeriods (bool): Si toutes les périodes doivent être récupérées. Par défaut, toutes les périodes sont récupérées.
		
	Returns:
		list[dict]: Les informations des punitions
	"""
	
	token = request.args.get('token')
	allPeriods = request.args.get('allPeriods', default=True)

	success, client = get_client(token)
	if success == 'ok':
		if allPeriods:
			allPunishments = [punishment for period in client.activated_period for punishment in period.punishments]
		else:
			allPunishments = client.calculated_period.punishments

		punishmentsData = []
		for punishment in allPunishments:
			homeworkDocs = []
			if punishment.homework_documents is not None:
				for homeworkDoc in punishment.homework_documents:
					homeworkDocs.append({
						"id": homeworkDoc.id,
						"name": homeworkDoc.name,
						"url": homeworkDoc.url,
						"type": homeworkDoc.type
					})

			circumstanceDocs = []
			if punishment.circumstance_documents is not None:
				for circumstanceDoc in punishment.circumstance_documents:
					circumstanceDocs.append({
						"id": circumstanceDoc.id,
						"name": circumstanceDoc.name,
						"url": circumstanceDoc.url,
						"type": circumstanceDoc.type
					})

			schedules = []
			if punishment.schedule is not None:
				for schedule in punishment.schedule:
					schedules.append({
						"id": schedule.id,
						"start": schedule.start.strftime("%Y-%m-%d %H:%M"),
						"duration": schedule.duration,
					})

			punishmentData = {
				"id": punishment.id,
				"schedulable": punishment.schedulable,
				"schedule": schedules,
				"date": punishment.given.strftime("%Y-%m-%d %H:%M"),
				"given_by": punishment.giver,
				"exclusion": punishment.exclusion,
				"during_lesson": punishment.during_lesson,
				"homework": {
					"text": punishment.homework,
					"documents": homeworkDocs,
				},
				"reason": {
					"text": punishment.reasons,
					"circumstances": punishment.circumstances,
					"documents": circumstanceDocs,
				},
				"nature": punishment.nature,
				"duration": punishment.duration
			}

			punishmentsData.append(punishmentData)

		return rjson(punishmentsData)
	else:
		return text('"'+success+'"', status=498)


@app.route('/news', methods=['GET'])
async def news(request):
	"""
	Récupère les actualités de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		list[dict]: Les informations des actualités
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		allNews = []
		try :
			allNews = client.information_and_surveys()
		except Exception as e:
			allNews = []

		newsAllData = []
		for news in allNews:
			local_id = ""

			try :
				local_id += news.title[:3]
			except Exception as e:
				local_id += ""

			local_id += news.creation_date.strftime("%Y-%m-%d_%H:%M")

			attachments = []
			if news.attachments is not None:
				for attachment in news.attachments:
					attachments.append({
						"id": attachment.id,
						"name": attachment.name,
						"url": attachment.url,
						"type": attachment.type
					})

			newsData = {
				"id": news.id,
				"local_id": local_id,
				"title": news.title,
				"date": news.creation_date.strftime("%Y-%m-%d %H:%M"),
				"category": news.category,
				"read": news.read,
				"survey": news.survey,
				"anonymous_survey": news.anonymous_response,
				"author": news.author,
				"content": news.content,
				"attachments": attachments,
				"html_content": news._raw_content
			}

			newsAllData.append(newsData)

		return rjson(newsAllData)
	else:
		return text('"'+success+'"', status=498)

@app.route('/news/markAsRead', methods=['POST'])
async def read_news(request):
	"""
	Change l'état de lecture d'une actualité.

	Args:
		token (str): Le token du client Pronote
		newsId (str): L'identifiant de l'actualité

	Returns:

	"""

	token = request.args.get('token')
	newsId = request.args.get('newsId')

	success, client = get_client(token)
	if success == 'ok':
		if client.logged_in:
			try:
				allNews = client.information_and_surveys()

				for news in allNews:
					local_id = ""

					# return a combination of the 20 first letters of content, 2 first letters of title and the date

					local_id += news.title[:3]
					local_id += news.creation_date.strftime("%Y-%m-%d_%H:%M")

					if local_id == newsId:
						current_state = news.read

						news.mark_as_read(not news.read)
						current_state = not news.read
							
						return rjson({
							"status": "ok",
							"current_state": current_state,
							"error": None
						})
				
				raise NotFound({
					"status": "not found",
					"error": "L'actualité n'a pas été trouvée."
				})
	
			except Exception as e:
				raise ServerError({
					"status": "error",
					"error": str(e)
				})

@app.route('/discussions', methods=['GET'])
async def discussions(request):
	"""
	Récupère les discussions de l'utilisateur.
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		list[dict]: Les informations des discussions :
		
		[{
			"id": str,
			"subject": str,
			"creator": str,
			"participants": list[str],
			"date": str,
			"unread": int,
			"replyable": bool,
			"messages": [{
				"id": str,
				"content": str,
				"author": str,
				"date": str,
				"seen": bool,
			}],
		}]
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		allDiscussions = []
		try :
			allDiscussions = client.discussions()
		except Exception as e:
			allDiscussions = []

		discussionsAllData = []
		for discussion in allDiscussions:
			messages = []
			for message in discussion.messages:
				messages.append({
					"id": message.id,
					"content": message.content,
					"author": message.author,
					"date": message.date.strftime("%Y-%m-%d %H:%M") if message.date is not None else None,
					"seen": message.seen
				})

			local_id = ""

			try:
				# return a combination of the 20 first letters of subject, 2 first letters of creator and the date
				local_id += discussion.subject[:3]
				local_id += discussion.creator[:3]
				local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")
			except Exception as e:
				local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")

			participants = []
			try :
				participants = discussion.participants()
			except Exception as e:
				participants = []

			discussionData = {
				"local_id": local_id,
				"subject": discussion.subject,
				"creator": discussion.creator,
				"date": discussion.date.strftime("%Y-%m-%d %H:%M") if discussion.date is not None else None,
				"unread": discussion.unread,
				"closed": discussion.close,
				"replyable": discussion.replyable,
				"messages": messages,
				"participants": participants
			}

			discussionsAllData.append(discussionData)

		return rjson(discussionsAllData)
	else:
		return text('"'+success+'"', status=498)


@app.route('/discussion/delete', methods=['POST'])
async def delete_discussion(request):
	"""
	Supprime une discussion.
	
	Args:
		token (str): Le token du client Pronote
		discussionId (str): L'identifiant de la discussion
		
	Returns:
		str: 'ok' si la discussion a été supprimée, 'not found' si la discussion n'a pas été trouvée, 'error' si une erreur est survenue.
	"""
	
	token = request.args.get('token')
	discussionId = request.args.get('discussionId')

	success, client = get_client(token)
	if success == 'ok':
		try:
			allDiscussions = client.discussions()
			for discussion in allDiscussions:
				local_id = ""

				try:
					# return a combination of the 20 first letters of subject, 2 first letters of creator and the date
					local_id += discussion.subject[:3]
					local_id += discussion.creator[:3]
					local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")
				except Exception as e:
					local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")

				if local_id == discussionId:
					discussion.delete()
					return rjson({
						"status": "ok",
						"error": None
					})
			
			raise NotFound({
				"status": "not found",
				"error": "La discussion n'a pas été trouvée."
			})
		except Exception as e:
			raise ServerError({
				"status": "error",
				"error": str(e)
			})

@app.route('/discussion/readState', methods=['POST'])
async def read_discussion(request):
	"""
	Change l'état de lecture d'une discussion.
	
	Args:
		token (str): Le token du client Pronote
		discussionId (str): L'identifiant de la discussion
		
	Returns:
		str: 'ok' si l'état de lecture a été changé, 'not found' si la discussion n'a pas été trouvée, 'error' si une erreur est survenue.
	"""
	
	token = request.args.get('token')
	discussionId = request.args.get('discussionId')

	success, client = get_client(token)
	if success == 'ok':
		try:
			allDiscussions = client.discussions()
			for discussion in allDiscussions:
				local_id = ""

				try:
					# return a combination of the 20 first letters of subject, 2 first letters of creator and the date
					local_id += discussion.subject[:3]
					local_id += discussion.creator[:3]
					local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")
				except Exception as e:
					local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")

				if local_id == discussionId:
					if discussion.unread == 0: 
						discussion.mark_as(False)
					else: 
						discussion.mark_as(True)
					return rjson({
						"status": "ok",
						"error": None
					})
			
			raise NotFound({
				"status": "not found",
				"error": "La discussion n'a pas été trouvée."
			})
		except Exception as e:
			raise ServerError({
				"status": "error",
				"error": str(e)
			})
	else:
		return text('"'+success+'"', status=498)

@app.route('/discussion/reply', methods=['POST'])
async def reply_discussion(request):
	"""
	Répond à une discussion.
	
	Args:
		token (str): Le token du client Pronote
		discussionId (str): L'identifiant de la discussion
		content (str): Le contenu du message
		
	Returns:
		str: 'ok' si le message a été envoyé, 'not replyable' si la discussion n'est pas ouverte à la réponse, 'not found' si la discussion n'a pas été trouvée, 'error' si une erreur est survenue.
	"""
	
	token = request.args.get('token')
	discussionId = request.args.get('discussionId')
	content = request.args.get('content')

	success, client = get_client(token)
	if success == 'ok':
		try:
			allDiscussions = client.discussions()
			for discussion in allDiscussions:
				local_id = ""

				try:
					# return a combination of the 20 first letters of subject, 2 first letters of creator and the date
					local_id += discussion.subject[:3]
					local_id += discussion.creator[:3]
					local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")
				except Exception as e:
					local_id += discussion.date.strftime("%Y-%m-%d_%H:%M")

				if local_id == discussionId:
					if discussion.replyable:
						discussion.reply(content)
						return rjson({
							"status": "ok",
							"error": None
						})
					else:
						raise Forbidden({
							"status": "not replyable",
							"error": "La discussion n'est pas ouverte à la réponse."
						})
			
			raise NotFound({
				"status": "not found",
				"error": "La discussion n'a pas été trouvée."
			})
		except Exception as e:
			raise ServerError({
				"status": "error",
				"error": str(e)
			})
	else:
		return text('"'+success+'"', status=498)


@app.route('/recipients', methods=['GET'])
async def recipients(request):
	"""
	Récupère la liste des destinataires possibles.
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		list: La liste des destinataires possibles.
		
		[{
			"id": str,
			"name": str,
			"type": str,
			"email": str,
			"functions": list[str],
			"with_discussion": bool
		}]
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		allRecipients = []
		try:
			allRecipients = client.get_recipients()
		except Exception as e:
			allRecipients = []

		recipientsAllData = []
		for recipient in allRecipients:
			recipientData = {
				"id": recipient.id,
				"name": recipient.name,
				"type": recipient.type,
				"email": recipient.email,
				"functions": recipient.functions,
				"with_discussion": recipient.with_discussion
			}

			recipientsAllData.append(recipientData)
		
		return rjson(recipientsAllData)
	else:
		return text('"'+success+'"', status=498)


@app.route('/discussion/create', methods=['POST'])
async def create_discussion(request):
	"""
	Créer une discussion.
	
	Args:
		token (str): Le token du client Pronote
		subject (str): Le sujet de la discussion
		content (str): Le contenu du message
		recipientsId (str): La liste des identifiants des destinataires ([id1, id2, id3])
		
	Returns:
		str: 'ok' si la discussion a été créée, 'error' si une erreur est survenue.
	"""
	
	token = request.args.get('token')
	subject = request.args.get('subject')
	content = request.args.get('content')
	recipientsId = request.args.get('recipientsId')

	success, client = get_client(token)
	if success == 'ok':
		try:
			prn_recipients = []
			for recipient in json_module.loads(recipientsId):
				for prn_recipient in client.get_recipients():
					if prn_recipient.id == recipient:
						prn_recipients.append(prn_recipient)
						
			if len(prn_recipients) == 0:
				raise BadRequest({
					"status": "no recipient",
					"error": "Aucun destinataire valide n'a été trouvé."
				})
				
			for prn_recipient in prn_recipients:
				if prn_recipient.with_discussion == False:
					raise BadRequest({
						"status": "recipient not accept discussion",
						"error": "Un ou plusieurs destinataires n'acceptent pas les discussions."
					})
					
			client.new_discussion(subject, content, prn_recipients)
			return rjson({
				"status": "ok",
				"error": None
			})
		except Exception as e:            
			raise ServerError({
				"status": "error",
				"error": str(e)
			})
	else:
		return text('"'+success+'"', status=498)


@app.route('/evaluations', methods=['GET'])
async def evaluations(request):
	"""
	Permet de récupérer les évaluations.
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		list[dict]: La liste des évaluations.
		
		[{
			"id": str,
			"subject": {
				"id": str,
				"name": str,
				"groups": bool
			},
			"name": str,
			"description": str,
			"teacher": str, 
			"date": str,
			"palier": str,
			"coefficient": str,
			"acquisitions": [{
				"id": str,
				"name": str,
				"coefficient": str,
				"abbreviation": str,
				"domain": str,
				"level": str
			}],
		}]
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		allEvaluations = []
		try :
			allEvaluations = client.calculated_period.evaluations
		except Exception as e:
			allEvaluations = []

		evaluationsAllData = []
		for evaluation in allEvaluations:
			acquisitions = []
			if evaluation.acquisitions is not None:
				for acquisition in evaluation.acquisitions:
					acquisitions.append({
						"id": acquisition.id,
						"name": acquisition.name,
						"coefficient": acquisition.coefficient,
						"abbreviation": acquisition.abbreviation,
						"domain": acquisition.domain,
						"level": acquisition.level
					})

			evaluationData = {
				"id": evaluation.id,
				"subject": {
					"id": evaluation.subject.id,
					"name": evaluation.subject.name,
					"groups": evaluation.subject.groups,
				},
				"name": evaluation.name,
				"description": evaluation.description,
				"teacher": evaluation.teacher,
				"date": evaluation.date.strftime("%Y-%m-%d %H:%M"),
				"paliers": evaluation.paliers,
				"coefficient": evaluation.coefficient,
				"acquisitions": acquisitions,
			}

			evaluationsAllData.append(evaluationData)

		return rjson(evaluationsAllData)
	else:
		return text('"'+success+'"', status=498)

def __get_meal_food(meal: list[dict]):
	"""
	Permet de récupérer les aliments d'un repas.
	
	Args:
		meal (list): La liste des aliments du repas
		
	Returns:
		list[dict]: La liste des aliments du repas.
	"""
	
	if meal is None:
		return None
	else:
		foods = []
		for food in meal:
			foods.append({
				"name": food.name,
				"labels": __get_food_labels(food.labels),
			})
		return foods

def __get_food_labels(labels: list[dict]):
	"""
	Permet de récupérer les labels d'un aliment.
	
	Args:
		labels (list): La liste des labels de l'aliment
		
	Returns:
		list[dict]: La liste des labels de l'aliment.
	"""
	
	if labels is None:
		return None
	else:
		foodLabels = []
		for label in labels:
			foodLabels.append({
				"id": label.id,
				"name": label.name,
				"color": label.color,
			})
		return foodLabels



@app.route('/export/ical', methods=['GET'])
async def export_ical(request):
	"""
	Permet d'exporter les données de Pronote en iCal. (si l'instance de Pronote le permet)
	
	Args:
		token (str): Le token du client Pronote
		
	Returns:
		str: L'URL de l'iCal.
	"""
	
	token = request.args.get('token')

	success, client = get_client(token)
	if success == 'ok':
		ical_url = client.export_ical()
		return rjson({"ical_url": ical_url})
	else:
		return text('"'+success+'"', status=498)

@app.route('/menu', methods=['GET'])
async def menu(request):
	"""
	Permet de récupérer les menus.
	
	Args:
		token (str): Le token du client Pronote
		dateFrom (str): La date de début
		dateTo (str): La date de fin
		
	Returns:
		list[dict]: La liste des menus.
		
		[{
			"id": str,
			"name": str,
			"date": str,
			"type": {
				"is_lunch": bool,
				"is_dinner": bool,
			},
			"first_meal": list[dict],
			"dessert": list[dict],
			"cheese": list[dict],
			"other_meal": list[dict],
			"side_meal": list[dict],
			"main_meal": list[dict],
		}]
	"""
	
	token = request.args.get('token')
	dateFrom = request.args.get('dateFrom')
	dateTo = request.args.get('dateTo')

	try :
		dateFrom = datetime.datetime.strptime(dateFrom, "%Y-%m-%d").date()
		dateTo = datetime.datetime.strptime(dateTo, "%Y-%m-%d").date()
	except Exception as e:
		dateFrom = datetime.datetime.now().date()
		dateTo = datetime.datetime.now().date()

	success, client = get_client(token)
	if success == 'ok':
		allMenus = client.menus(date_from=dateFrom, date_to=dateTo)

		menusAllData = []
		for menu in allMenus:
			cheese = __get_meal_food(menu.cheese)
			dessert = __get_meal_food(menu.dessert)
			other_meal = __get_meal_food(menu.other_meal)
			side_meal = __get_meal_food(menu.side_meal)
			main_meal = __get_meal_food(menu.main_meal)
			first_meal = __get_meal_food(menu.first_meal)

			menuData = {
				"id": menu.id,
				"name": menu.name,
				"date": menu.date.strftime("%Y-%m-%d"),
				"type": {
					"is_lunch": menu.is_lunch,
					"is_dinner": menu.is_dinner,
				},
				"first_meal": first_meal,
				"dessert": dessert,
				"cheese": cheese,
				"other_meal": other_meal,
				"side_meal": side_meal,
				"main_meal": main_meal,
			}

			menusAllData.append(menuData)

		return rjson(menusAllData)
	else:
		return text('"'+success+'"', status=498)
	

@app.route('/homework/changeState', methods=['POST'])
async def set_homework_as_done(request):
	"""
	Change l'état d'un devoir. (fait ou non fait)
	
	Args:
		token (str): Le token du client Pronote
		dateFrom (str): La date de début
		dateTo (str): La date de fin
		homeworkId (str): Le LocaID du devoir
		
	Returns:
		str: 'ok' si tout s'est bien passé, 'not found' si le devoir n'a pas été trouvé, 'error' si une erreur est survenue.
	"""
	
	token = request.args.get('token')
	dateFrom = request.args.get('dateFrom')
	dateTo = request.args.get('dateTo')
	homeworkId = request.args.get('homeworkId')

	try :
		dateFrom = datetime.datetime.strptime(dateFrom, "%Y-%m-%d").date()
		dateTo = datetime.datetime.strptime(dateTo, "%Y-%m-%d").date()
	except Exception as e:
		dateFrom = datetime.datetime.now().date()
		dateTo = datetime.datetime.now().date()

	success, client = get_client(token)

	if success == 'ok':
		if client.logged_in:
			try:
				homeworks = []
				try :
					homeworks = client.homework(date_from=dateFrom, date_to=dateTo)
				except Exception as e:
					homeworks = []
				changed = False

				for homework in homeworks:
					local_id = ""

					# return a combination of the 20 first letters of description, 2 first letters of subject name and the date
					if len(homework.description) > 20:
						local_id += homework.description[:20]
					else:
						local_id += homework.description
					
					local_id += homework.subject.name[:2]
					local_id += homework.date.strftime("%Y-%m-%d_%H:%M")
					
					if local_id == homeworkId:
						current_state = homework.done
						if homework.done:
							homework.set_done(False)
							current_state = False
						else:
							homework.set_done(True)
							current_state = True
						changed = True
						return rjson({
							"status": "ok",
							"current_state": current_state,
							"error": None
						})
				if not changed:
					raise NotFound("Aucun devoir trouvé avec cet ID local.")
			except Exception as e:
				raise ServerError(str(e))
	else:
		return text('"'+success+'"', status=498)

def main():
	app.run(host="0.0.0.0", port=8000, single_process=True)

if __name__ == '__main__':
	main()