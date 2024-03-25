import express, { Request, Response } from 'express';
import axios from 'axios';
import * as fs from 'fs';

const app = express();
const PORT = 3000;

// Liste des mainteneurs
const mainteneurs = ['Vilerio', 'ecnivtwelve', 'maelgangloff', 'tryon-dev'];

// Liste des contributeurs vérifiés
const contributeursVerifies = ['lucas-luchack', 'Rexxt', 'skythrew', 
                               'tom-theret', 'LeMaitre4523', 'yannouuuu', 
                               'oriionn', 'LeGeek01', 'Vexcited', 
                               'NonozgYtb', 'Ahhj93', 'godetremy', ];

// Fonction pour lire un fichier JSON
function responseFile(path: string): any {
    return JSON.parse(fs.readFileSync(path, "utf8"));
}

// Fonction pour obtenir le rôle du contributeur en fonction de son nom
function getRole(name: string): string {
    if (mainteneurs.includes(name)) {
        return 'Mainteneur';
    } else if (contributeursVerifies.includes(name)) {
        return 'Contributeur vérifié';
    } else {
        return 'Contributeur';
    }
}

app.get('/', (req: Request, res: Response) => {
    res.send('PapiAPI est joignable !');
});

app.get('/team', async (req: Request, res: Response) => {
    try {
        const response = await axios.get('https://api.github.com/repos/PapillonApp/Papillon/contributors');
        const teamData = response.data.reduce((acc: any, contributor: any) => {
            const role = getRole(contributor.login);
            const member = { name: contributor.login, role, avatar: contributor.avatar_url, link: contributor.html_url };
            if (role === 'Mainteneur') {
                acc[0].member.push(member);
            } else if (role === 'Contributeur vérifié') {
                acc[1].member.push(member);
            } else {
                acc[2].member.push(member);
            }
            return acc;
        }, [
            { name: 'Mainteneurs', member: [] },
            { name: 'Contributeurs Vérifiés', member: [] },
            { name: 'Contributeurs', member: [] }
        ]);
        const teamJson = {
            lastupdated: new Date().toISOString(),
            team: teamData
        };
        res.json(teamJson);
    } catch (error) {
        res.status(500).json({ error: 'Une erreur s\'est produite lors de la récupération des données de l\'équipe depuis GitHub.' });
    }
});

// Renvoie le contenu du fichier JSON des messages
app.get('/messages', (req: Request, res: Response) => {
    res.json(responseFile("data/json/messages.json"));
});

// Renvoie le contenu du fichier JSON de la dernière version pour une plateforme donnée
app.get('/latestVersion/:platform', (req: Request, res: Response) => {
    res.json(responseFile(`data/json/latestVersion${req.params.platform}.json`));
});

// Renvoie le contenu du fichier JSON du personnel avec le nom spécifié dans le paramètre
app.get('/staff/:name/photo', (req: Request, res: Response) => {
    res.json(responseFile(`data/img/staff_${req.params.name}.json`));
});

app.listen(PORT, () => {
    console.log(`PapiAPI est joignable via le port ${PORT} !`);
});
