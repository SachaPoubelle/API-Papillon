#!/bin/bash

echo "Papillon    ^=^z    EN COURS : Mise à jour du repo api Papillon"

start_api() {
    kill -9 $(netstat -nlp | awk '/:8000/ {split($NF,a,"/"); print a[1]}')
    rm -rf papillon-python
    pip install --upgrade pip
    pip uninstall pronotepy -y
    git clone -b development https://github.com/PapillonApp/papillon-python
    pip3.11 install -U https://github.com/bain3/pronotepy/archive/refs/heads/master.zip
    pip3.11 install -U lxml sentry-sdk redis sanic
    cd papillon-python
    echo "Papillon    ^|^e   Lancement de l'API"
    #python3.11 -m hug -f server.py
    sanic server
}

while true; do
    start_api
    echo "Si vous souhaitez arrêter complètement le processus API maintenant, appuyez sur Ctrl+C avant la fin du compte à rebours !"
    for i in 5 4 3 2 1; do
        echo "Papillon    ^=^z    Redémarrage dans $i"
        sleep 1
    done
    echo "Papillon    ^=^z    Redémarrage de l'API"
done
