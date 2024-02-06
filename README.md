![image](https://github.com/PapillonApp/papillon-python/assets/32978709/e7317645-e47c-4728-b7cd-9de53a24a11e)

## Pourquoi faire ?
Auparavant, [Papillon](https://github.com/ecnivtwelve/Papillon) utilisait [@Litarvan/pronote-api](https://github.com/Litarvan/pronote-api), mais cette API non maintenue depuis Avril 2021 commence à poser de plus en plus de problèmes à cause de son retard, et en plus est compliquée à héberger. Voila pourquoi je transitionne vers [@bain3/pronotepy](https://github.com/bain3/pronotepy), qui est encore maintenu et bien plus complet en fonctionnalités.

Cela permet aussi à vous, utilisateurs et utilisatrices de Papillon, d'utiliser **votre propre serveur** afin de faire fonctionner notre application et ainsi **ne plus être dépendant** de notre infrastructure.

> ⚠️ **Attention :** *Si vous décidez d'utiliser votre propre instance de notre API nous ne seront pas en mesure de vous aider et nous ne proposerons aucun support concernant l'utilisation de l'API et les problèmes qui pourrait vous arriver suite à votre propre gestion de cette dernière.*

## Déploiement
### Pré-requis

Vous devez installer **Python 3.10 minimum** et **PiP**.<br/>
Ensuite installer les dépendances avec les commandes suivantes :

```sh
pip3 install hug -U
pip3 install pronotepy -U
pip3 install lxml
```

## Installation
### Bare-metal
Une fois les pré-requis en place vous pouvez executer le serveur avec la commande suivante :
Veuillez noter que le serveur est prévu pour fonctionner sur notre infrastructure, il est donc possible que vous deviez modifier le code pour qu'il fonctionne sur votre propre serveur. De plus, il est **nécessaire** de modifier le fichier `server.py` et de supprimer les fonctions `get_client_on_instances()` et `token_get_client()` ainsi que les appels à ces fonctions *(si présent dans la branche téléchargée)*.
```sh
git clone -b main https://github.com/PapillonApp/papillon-python
cd papillon-python
python -m hug -f server.py
```
*Cela va lancer le serveur sur le port 8000.*

### Docker
Une fois docker installé sur votre machine, vous pouvez pull l'image docker : 
```sh
docker pull justtryon/papillonserver:latest
```
Une fois cela fait, vous pouvez déployer l'api avec cette commande : 
```sh
docker run -d -p 8000:8000 -e CRON="*/15 * * * *" justtryon/papillonserver:latest
```
*Vous pouvez changer le temps de redémarrage automatique du serveur en changeant la variable d'environnement CRON*

*Cela va lancer le serveur sur le port 8000.*


## Documentation
### Requêtes
Un client doit faire la requête initiale `POST /generatetoken` avec le body suivant :
| Paramètre | Utilité | Exemple |
|--|--|--|
| `url: str(url)` | URL vers l'instance pronote **(avec le eleve.html)** | `https://0152054e.index-education.net/pronote/eleve.html` |
| `username: str` | Nom d'utilisateur **PRONOTE** | `l.martin` |
| `password: str` | Mot de passe en clair | `azertyuiop12345` |
| `ent: str(ent)` | Nom de l'ENT tel que listé [ici](https://github.com/bain3/pronotepy/blob/master/pronotepy/ent/ent.py) | `ac_rennes` |

Le client doit ensuite garder le token généré. Si il ya eu un délai d'au moins 5 minutes entre deux interactions, le client doit regénérer un nouveau token.

Ensuite chaque appel à une fonction de l'API doit avoir le paramètre `token` défini.
Voici la liste des URLs pour obtenir des données :

| URL | Utilité | Paramètres |
|--|--|--|
| `/user` | Obtient les infos sur l'utilisateur (nom, classe...) + les périodes de l'année |  |
| `/timetable` | Affiche l'emploi du temps sur une date donnée | `dateString: str` : date au format **`année-mois-jour`** |
| `/homework` | Affiche les devoirs entre deux dates données | `dateFrom: str` : date de début au format **`année-mois-jour`**, et `dateTo: str` : date de fin au même format |
| `/grades` | Affiche les notes |  |
| `/evaluations` | Affiche les évaluations par compétences |  |
| `/absences` | Affiche les absences |  |
| `/punishments` | Affiche les punitions |  |
| `/news` | Affiche les actualités |  |
| `/discussions` | Affiche les messages |  |
| `/menu` | Affiche les menus entre deux dates données | `dateFrom: str` : date de début au format **`année-mois-jour`**, et `dateTo: str` : date de fin au même format |
| `/recipients` | Liste toutes les personnes que l'utilisateur peut contacter par message |  |

Voici la liste des URL qui éffectuent une simple fonction :
| URL | Utilité | Paramètres | Réponse
|--|--|--|--|
| `/info` | Envoie des informations sur l'API comme les ENTs et la version |  |  |
| `/export/ical` | Exporte le calendrier en iCal |  | *(l'url du fichier iCal)* |
| `/homework/changeState` | Change l'état d'un devoir (fait/non fait) | `dateFrom: str` : date de début au format **`année-mois-jour`**, et `dateTo: str` date de fin au même format, et `homeworkId: str` l'id du devoir à changer | *(état du devoir changé)* |
| `/discussion/delete` | Supprime la discussion | `discussionId: str` : Id de la discussion | `ok` si aucun problème |
| `/discussion/readState` | Change l'état de lecture d'une discussion | `discussionId: str` : Id de la discussion | `ok` si aucun problème |
| `/discussion/reply` | Répond à une discussion | `discussionId: str` : Id de la discussion, et `content: str` : Contenu du message | `ok` si aucun problème |
| `/discussion/create` | Crée une discussion | `recipientId: str` : Id du destinataire, `content: str` : Contenu du message et `recipients: list` : La liste de destinataire avec leurs ID (obtenu avec `/recipients`) | `ok` si aucun problème |
