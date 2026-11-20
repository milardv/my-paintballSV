// Tests d'intégration contre `wrangler dev` (MODE_DEV=1) : auth, liste, salons, CSRF, manches complètes.
// node outils/test-integration.mjs [http://127.0.0.1:8787]
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFileSync } from 'node:fs';
import { Client, Socket, viser, pause } from './client.mjs';

// fetch et WebSocket de Node ne laissent pas fixer l'en-tête Origin : requête HTTP brute.
function brute(methode, chemin, entetes, corps) {
  return new Promise((ok, ko) => {
    const r = http.request(BASE + chemin, { method: methode, headers: entetes }, rep => { rep.resume(); ok(rep.statusCode); });
    r.on('upgrade', rep => { rep.socket?.destroy(); ok(rep.statusCode); });
    r.on('error', ko);
    r.end(corps);
  });
}

const BASE = process.argv[2] ?? 'http://127.0.0.1:8787';
const ADMIN = process.env.ADMIN_EMAIL ?? 'admin@exemple.fr';   // même valeur que ADMIN_EMAIL de wrangler.toml
const suffixe = Date.now().toString(36);
const AMI = `ami-${suffixe}@test.fr`;
const INCONNU = `inconnu-${suffixe}@test.fr`;
let ok = 0;

async function etape(nom, f) {
  try {
    await f();
    ok++;
    console.log('ok  ', nom);
  } catch (e) {
    console.log('ECHEC', nom);
    console.error(e);
    process.exit(1);
  }
}

const admin = new Client(BASE);
const ami = new Client(BASE);
const inconnu = new Client(BASE);
let salon, autreSalon, lien, autreLien;
// Un fichier du build préparé dans jeu/ (npm run preparer-jeu).
const FICHIER_JEU = '/' + Object.keys(JSON.parse(readFileSync(new URL('../jeu/manifeste.json', import.meta.url)))).find(k => k.startsWith('Build/'));
const texte = async r => (await r.text());

await etape('sans session : 401', async () => {
  assert.equal((await new Client(BASE).get('/api/moi')).status, 401);
});

await etape('sans session : aucun fichier du jeu, page de connexion', async () => {
  const c = new Client(BASE);
  const r = await c.get('/?salon=ab');
  assert.equal(r.status, 401);
  const html = await texte(r);
  assert.match(html, /Se connecter avec Google/);
  assert.match(html, /\/auth\/google\?retour=%2F%3Fsalon%3Dab/);
  assert.doesNotMatch(html, /Build\//);
  assert.equal((await c.get('/index.html')).status, 401);
  assert.equal((await c.get(FICHIER_JEU)).status, 401);
  assert.equal((await c.get('/reseau.js')).status, 401);
});

await etape('e-mail hors liste refusé', async () => {
  const r = await inconnu.connexionDev(INCONNU);
  assert.equal(r.status, 403);
  assert.match(await texte(r), /Accès non autorisé[\s\S]*Changer de compte Google/);
  assert.equal(inconnu.cookies.size, 0);
  assert.equal((await inconnu.get('/')).status, 401);
});

await etape('e-mail invalide refusé', async () => {
  assert.equal((await new Client(BASE).connexionDev('pas-un-email')).status, 400);
});

await etape('admin de configuration', async () => {
  assert.equal((await admin.connexionDev(ADMIN.toUpperCase(), 'Valentin')).status, 303);
  assert.equal(admin.moi.admin, true);
  assert.equal(admin.moi.email, ADMIN);
  const c = admin.cookies.get('__Host-psv');
  assert.ok(c && admin.csrf);
  assert.equal((await admin.get('/')).status, 200);
  const f = await admin.get(FICHIER_JEU);
  assert.equal(f.status, 200);
  assert.match(f.headers.get('cache-control'), /^private/);
});

await etape('cookie de session HttpOnly, Secure, SameSite=Lax', async () => {
  const rep = await new Client(BASE).get('/auth/dev?nom=Valentin&email=' + encodeURIComponent(ADMIN));
  const c = rep.headers.getSetCookie().find(x => x.startsWith('__Host-psv='));
  assert.match(c, /HttpOnly/);
  assert.match(c, /Secure/);
  assert.match(c, /SameSite=Lax/);
  assert.match(c, /Path=\//);
});

await etape('jeton de session falsifié refusé', async () => {
  const faux = new Client(BASE);
  const [charge, sig] = admin.cookies.get('__Host-psv').split('.');
  const donnees = JSON.parse(Buffer.from(charge, 'base64url'));
  donnees.email = 'pirate@test.fr';
  faux.cookies.set('__Host-psv', Buffer.from(JSON.stringify(donnees)).toString('base64url') + '.' + sig);
  assert.equal((await faux.get('/api/moi')).status, 401);
});

await etape('CSRF : POST sans jeton ou depuis une autre origine refusé', async () => {
  assert.equal((await admin.post('/api/salons', { nom: 'x' }, { csrf: false })).status, 403);
  assert.equal((await admin.post('/api/salons', { nom: 'x' }, { extra: { 'x-csrf': 'faux' } })).status, 403);
  const h = admin.entetes({ 'content-type': 'application/json', 'x-csrf': admin.csrf });
  assert.equal(await brute('POST', '/api/salons', { ...h, origin: 'https://evil.example' }, '{}'), 403);
});

await etape('admin crée deux salons, lien permanent et QR code', async () => {
  assert.equal((await admin.post('/api/salons', { nom: '   ' })).status, 400);
  const r = await admin.post('/api/salons', { nom: '  Salon   du château ' });
  assert.equal(r.status, 201);
  const c = await admin.json(r);
  assert.equal(c.nom, 'Salon du château');
  assert.match(c.lien, /\/s\/[A-Za-z0-9_-]{20,}$/);
  assert.match(c.qr_svg, /^<\?xml|<svg/);
  salon = c.id;
  lien = c.lien;
  const autre = await admin.json(await admin.post('/api/salons', { nom: 'Autre' }));
  autreSalon = autre.id;
  autreLien = autre.lien;
  const liste = await admin.json(await admin.get('/api/salons'));
  const s = liste.salons.find(x => x.id === salon);
  assert.equal(s.lien, lien);
  assert.equal(s.membres, 1, 'l\'admin est membre de ses salons');
  assert.equal(s.cle, undefined);
  const qr = await admin.get(`/api/salons/${salon}/qr.svg`);
  assert.equal(qr.headers.get('content-type'), 'image/svg+xml');
});

await etape('liste autorisée : ajout par l\'admin', async () => {
  // Le rôle admin ne se délègue pas : le champ est ignoré.
  const r = await admin.post('/api/autorises', { email: ` ${AMI.toUpperCase()} `, admin: true });
  assert.equal(r.status, 200);
  assert.equal((await admin.json(r)).admin, undefined);
  const l = await admin.json(await admin.get('/api/autorises'));
  assert.ok(l.autorises.some(a => a.email === AMI));
  assert.equal((await admin.post('/api/autorises', { email: 'pas valide' })).status, 400);
});

await etape('inscrit : connexion, pas de droits admin, aucun salon visible', async () => {
  assert.equal((await ami.connexionDev(AMI, 'Ami')).status, 303);
  assert.equal(ami.moi.admin, false);
  assert.equal(ami.moi.droit, 'autorise');
  assert.equal((await ami.get('/')).status, 200, 'un inscrit voit le jeu');
  assert.equal((await ami.post('/api/autorises/retirer', { email: ADMIN })).status, 403);
  assert.equal((await ami.post('/api/salons', { nom: 'x' })).status, 403);
  assert.equal((await ami.post('/api/autorises', { email: 'x@y.fr' })).status, 403);
  assert.equal((await ami.get('/api/autorises')).status, 403);
  assert.deepEqual((await ami.json(await ami.get('/api/salons'))).salons, []);
  assert.equal((await ami.get(`/api/salons/${salon}`)).status, 404, 'pas encore membre');
  assert.equal((await ami.ticket(salon)).rep.status, 404);
  assert.equal((await ami.get(`/api/salons/${salon}/qr.svg`)).status, 403);
  assert.equal((await ami.post(`/api/salons/${salon}/supprimer`)).status, 403);
});

const chemin = l => new URL(l).pathname;

await etape('inscrit qui ouvre le lien : membre du salon', async () => {
  const r = await ami.get(chemin(lien));
  assert.equal(r.status, 303);
  assert.match(r.headers.get('location'), new RegExp(`/\\?salon=${salon}$`));
  const l = await ami.json(await ami.get('/api/salons'));
  assert.deepEqual(l.salons.map(x => x.id), [salon]);
  const d = await ami.json(await ami.get(`/api/salons/${salon}`));
  assert.equal(d.salon.nom, 'Salon du château');
  assert.equal(d.lien, undefined, 'lien réservé à l\'admin');
  assert.ok(d.membres.some(m => m.pseudo === 'Ami'));
  assert.ok(!JSON.stringify(d).includes('@'), 'aucun e-mail exposé');
});

/** Entrée d'un invité par le lien : session invité, sans Google. */
async function entrerParLien(l) {
  const c = new Client(BASE);
  const r = await c.get(chemin(l));
  if (r.status === 303) {
    c.moi = await c.json(await c.get('/api/moi'));
    c.csrf = c.moi.csrf;
  }
  return { c, r };
}

await etape('lien sans session : invité sans Google, accès au salon et au jeu entier', async () => {
  const { c, r } = await entrerParLien(lien);
  assert.equal(r.status, 303);
  assert.match(r.headers.get('location'), new RegExp(`/\\?salon=${salon}$`));
  assert.match(r.headers.getSetCookie().find(x => x.startsWith('__Host-psv=')), /HttpOnly/);
  assert.equal(c.moi.droit, 'membre');
  assert.equal(c.moi.invite, true);
  assert.equal(c.moi.email, null);
  assert.equal((await c.get('/')).status, 200);
  assert.equal((await c.get(FICHIER_JEU)).status, 200);
  assert.deepEqual((await c.json(await c.get('/api/salons'))).salons.map(x => x.id), [salon]);
  assert.equal((await c.get(`/api/salons/${autreSalon}`)).status, 404);
  assert.equal((await c.post('/api/salons', { nom: 'x' })).status, 403);
  assert.equal((await c.get('/api/autorises')).status, 403);
  assert.equal((await c.ticket(salon)).rep.status, 200);
  // Sans lien ni connexion : rien n'est servi.
  assert.equal((await new Client(BASE).get('/')).status, 401);
});

await etape('lien inconnu : 410', async () => {
  assert.equal((await ami.get('/s/inconnu')).status, 410);
  assert.equal((await ami.get('/s/' + 'x'.repeat(200))).status, 410);
});

await etape('hors liste + lien : membre, accès au jeu entier', async () => {
  const r = await inconnu.connexionDev(INCONNU, 'Invité', chemin(lien).split('/s/')[1]);
  assert.equal(r.status, 303);
  assert.match(r.headers.get('location'), new RegExp(`salon=${salon}`));
  assert.equal(inconnu.moi.droit, 'membre');
  assert.equal((await inconnu.get('/')).status, 200, 'jeu entier : exploration et bots');
  assert.equal((await inconnu.get(FICHIER_JEU)).status, 200);
  assert.equal((await inconnu.get(`/api/salons/${salon}`)).status, 200);
  assert.equal((await inconnu.get(`/api/salons/${autreSalon}`)).status, 404);
  assert.equal((await inconnu.ticket(autreSalon)).rep.status, 404);
  assert.equal((await inconnu.post('/api/salons', { nom: 'x' })).status, 403);
  // Reconnexion ultérieure sans lien : toujours membre.
  assert.equal((await new Client(BASE).connexionDev(INCONNU)).status, 303);
});

await etape('lien régénéré : ancien lien invalide, invités exclus, inscrits gardés', async () => {
  const { c } = await entrerParLien(autreLien);
  const t = (await c.ticket(autreSalon)).corps;
  const sock = await Socket.ouvrir(t.ws.replace('ws://localhost:8787', BASE.replace('http', 'ws')));
  await sock.type('bienvenue');
  assert.equal((await ami.post(`/api/salons/${autreSalon}/lien`)).status, 403);
  const r = await admin.post(`/api/salons/${autreSalon}/lien`);
  assert.equal(r.status, 200);
  const nouveau = (await admin.json(r)).lien;
  assert.notEqual(nouveau, autreLien);
  assert.equal((await sock.type('fermeture')).code, 4005);
  assert.equal((await c.get('/api/moi')).status, 401, 'session invité révoquée');
  assert.equal((await new Client(BASE).get(chemin(autreLien))).status, 410);
  autreLien = nouveau;
  assert.equal((await entrerParLien(autreLien)).r.status, 303);
});

await etape('suppression du salon : lien invalide, accès retiré', async () => {
  const { c } = await entrerParLien(autreLien);
  const t = (await c.ticket(autreSalon)).corps;
  const s = await Socket.ouvrir(t.ws.replace('ws://localhost:8787', BASE.replace('http', 'ws')));
  await s.type('bienvenue');
  assert.equal((await admin.post(`/api/salons/${autreSalon}/supprimer`)).status, 200);
  assert.equal((await s.type('fermeture')).code, 4004);
  assert.equal((await c.get('/api/moi')).status, 401, 'plus aucun droit');
  assert.equal((await c.get('/')).status, 401);
  assert.equal((await c.get(chemin(autreLien))).status, 410);
  assert.equal((await admin.get(`/api/salons/${autreSalon}`)).status, 404);
});

await etape('retrait de la liste : sessions révoquées', async () => {
  const tmp = `temp-${suffixe}@test.fr`;
  await admin.post('/api/autorises', { email: tmp });
  const c = new Client(BASE);
  assert.equal((await c.connexionDev(tmp)).status, 303);
  assert.equal((await admin.post('/api/autorises/retirer', { email: tmp })).status, 200);
  assert.equal((await c.get('/api/moi')).status, 401);
  assert.equal((await new Client(BASE).connexionDev(tmp)).status, 403);
  assert.equal((await admin.post('/api/autorises/retirer', { email: ADMIN })).status, 400);
});

await etape('déconnexion', async () => {
  const c = new Client(BASE);
  await c.connexionDev(AMI);
  assert.equal((await c.post('/auth/deconnexion')).status, 200);
  assert.equal((await c.get('/api/moi')).status, 401);
});

await etape('WebSocket : ticket requis, lié au salon, origine contrôlée', async () => {
  const t = (await admin.ticket(salon)).corps;
  const ws = base => base.replace('http', 'ws');
  const essai = async (url, opts) => {
    try { const s = await Socket.ouvrir(url, opts); s.fermer(); return 'ouvert'; } catch { return 'refusé'; }
  };
  assert.equal(await essai(`${ws(BASE)}/api/salons/${salon}/ws`), 'refusé');
  assert.equal(await essai(`${ws(BASE)}/api/salons/${autreSalon}/ws?ticket=${t.ticket}`), 'refusé');
  const amont = { connection: 'Upgrade', upgrade: 'websocket', 'sec-websocket-version': '13', 'sec-websocket-key': 'dGhlIHNhbXBsZSBub25jZQ==' };
  assert.equal(await brute('GET', `/api/salons/${salon}/ws?ticket=${t.ticket}`, { ...amont, origin: 'https://evil.example' }), 403);
  assert.equal(await brute('GET', `/api/salons/${salon}/ws?ticket=${t.ticket}`, { ...amont, origin: 'http://localhost:8787' }), 101);
});

// ---------- Salon : profils, manches, entrée en cours ----------

const joueurs = {};
async function connecter(nom, client) {
  const { corps } = await client.ticket(salon);
  const url = corps.ws.replace('ws://localhost:8787', BASE.replace('http', 'ws'));
  const s = await Socket.ouvrir(url);
  const b = await s.type('bienvenue');
  joueurs[nom] = { s, j: b.j, client, pos: null, bienvenue: b };
  return joueurs[nom];
}

await etape('arrivée dans le salon : pseudo par défaut, couleurs distinctes', async () => {
  const a = await connecter('admin', admin);
  const b = await connecter('ami', ami);
  assert.equal(a.bienvenue.salon.nom, 'Salon du château');
  assert.equal(a.bienvenue.pseudo, 'Valentin');
  assert.equal(b.bienvenue.pseudo, 'Ami');
  assert.notEqual(a.bienvenue.c, b.bienvenue.c);
  const etat = await a.s.attendre(m => m.t === 'etat' && m.joueurs.length === 2);
  assert.equal(etat.phase, 'attente');
  assert.equal(etat.manche, 0);
  assert.ok(!JSON.stringify(etat).includes('@'), 'aucun e-mail diffusé');
});

await etape('profil : pseudo et couleur modifiables, contrôlés, enregistrés', async () => {
  const a = joueurs.admin, b = joueurs.ami;
  b.s.envoyer({ t: 'profil', pseudo: 'valentin' });
  assert.equal((await b.s.type('refus')).raison, 'pseudo pris');
  b.s.envoyer({ t: 'profil', c: a.bienvenue.c });
  assert.equal((await b.s.type('refus')).raison, 'couleur prise');
  b.s.envoyer({ t: 'profil', pseudo: '<img>' });
  assert.equal((await b.s.type('refus')).raison, 'pseudo invalide');
  b.s.envoyer({ t: 'profil', pseudo: '  Max  la Menace ', c: 4 });
  const e = await a.s.attendre(m => m.t === 'etat' && m.joueurs.some(x => x.pseudo === 'Max la Menace'));
  assert.equal(e.joueurs.find(x => x.j === b.j).c, 4);
  await pause(200);
  const d = await ami.json(await ami.get(`/api/salons/${salon}`));
  assert.ok(d.membres.some(m => m.pseudo === 'Max la Menace' && m.c === 4), JSON.stringify(d.membres));
});

await etape('ping/pong horodaté', async () => {
  const a = joueurs.admin;
  a.s.envoyer({ t: 'ping', c: 42.5 });
  const p = await a.s.type('pong');
  assert.equal(p.c, 42.5);
  assert.ok(Math.abs(p.h - Date.now()) < 5000);
});

const SPAWNS = [[0, 0, 0, 0], [12, 0, 0, 90], [0, 0, 12, 180], [12, 0, 12, 270], [6, 0, 20, 0], [20, 0, 6, 0]];
let boucle;
function suivrePositions() {
  let q = 0;
  for (const x of Object.values(joueurs)) {
    x.s.surMessage = m => {
      if ((m.t === 'touche' && m.cible === x.j && m.spawn) || (m.t === 'entree' && m.j === x.j)) x.pos = m.spawn.slice(0, 3);
    };
  }
  clearInterval(boucle);
  boucle = setInterval(() => {
    q++;
    for (const x of Object.values(joueurs)) if (x.pos) x.s.envoyer({ t: 'p', q, p: x.pos, r: [0, 0], v: [0, 0, 0] });
  }, 50);
}

await etape('manche 1 lancée par un membre (pas l\'admin) : cible 3, 3 vies', async () => {
  joueurs.ami.s.envoyer({ t: 'lancer', spawns: SPAWNS });
  for (const x of Object.values(joueurs)) {
    const d = await x.s.type('debut');
    assert.equal(d.manche, 1);
    assert.equal(d.cible, 3);
    assert.equal(d.vies, 3);
    x.pos = d.joueurs.find(p => p.j === x.j).spawn.slice(0, 3);
  }
  suivrePositions();
  await pause(1700); // protection de départ
});

let tirId = 1;
async function tirer(tireur, cible) {
  const o = [tireur.pos[0], tireur.pos[1] + 1.3, tireur.pos[2]];
  const visee = viser(o, [cible.pos[0], cible.pos[1] + 1.0, cible.pos[2]]);
  const id = tirId++;
  tireur.s.envoyer({ t: 'tir', id, o, d: visee.d, v: 85.344 });
  await pause(visee.t * 1000 + 30);
  tireur.s.envoyer({ t: 'touche', tir: id, cible: cible.j, pt: visee.pt });
  return tireur.s.attendre(m => (m.t === 'touche' && m.tir === id) || m.t === 'refus');
}

await etape('relais des positions et des tirs', async () => {
  const lot = await joueurs.ami.s.attendre(m => m.t === 'ps' && m.l.some(x => x.j === joueurs.admin.j));
  const p = lot.l.find(x => x.j === joueurs.admin.j);
  assert.deepEqual(p.p, joueurs.admin.pos);
  joueurs.ami.s.envoyer({ t: 'tir', id: 999, o: [joueurs.ami.pos[0], 1.3, joueurs.ami.pos[2]], d: [1, 0, 0] });
  const t = await joueurs.admin.s.attendre(m => m.t === 'tir' && m.id === 999);
  assert.equal(t.j, joueurs.ami.j);
});

await etape('touche invalide refusée (point hors trajectoire)', async () => {
  const a = joueurs.admin, b = joueurs.ami;
  const o = [a.pos[0], 1.3, a.pos[2]];
  a.s.envoyer({ t: 'tir', id: 500, o, d: [0, 1, 0] });
  a.s.envoyer({ t: 'touche', tir: 500, cible: b.j, pt: [b.pos[0], 1.0, b.pos[2]] });
  assert.equal((await a.s.type('refus')).raison, 'hors trajectoire');
});

await etape('touche validée : qui et d\'où', async () => {
  const t = await tirer(joueurs.admin, joueurs.ami);
  assert.equal(t.t, 'touche', JSON.stringify(t));
  assert.equal(t.tireur, joueurs.admin.j);
  assert.equal(t.o.length, 3);
  assert.equal(t.vies, 2);
  assert.equal(t.points, 1);
  await pause(1700);
});

await etape('entrée en cours de manche : 3 vies, cible recalculée (3 → 4)', async () => {
  const c = await connecter('invite', inconnu);
  assert.equal(c.bienvenue.en_jeu, false);
  const e0 = await c.s.attendre(m => m.t === 'etat' && m.phase === 'en_cours');
  assert.equal(e0.manche, 1);
  c.s.envoyer({ t: 'tir', id: 1, o: [0, 1.3, 0], d: [1, 0, 0] });
  assert.equal((await c.s.type('refus')).raison, 'hors manche', 'spectateur avant d\'entrer');
  c.s.envoyer({ t: 'entrer' });
  for (const x of Object.values(joueurs)) {
    const e = await x.s.attendre(m => m.t === 'entree');
    assert.equal(e.j, c.j);
    assert.equal(e.cible, 4);
    if (x === c) x.pos = e.spawn.slice(0, 3);
  }
  const etat = await joueurs.admin.s.attendre(m => m.t === 'etat' && m.joueurs.some(x => x.j === c.j && x.en_jeu));
  assert.equal(etat.joueurs.find(x => x.j === c.j).vies, 3);
  suivrePositions();
  c.s.envoyer({ t: 'entrer' });
  assert.equal((await c.s.type('refus')).raison, 'déjà en jeu');
  await pause(1700);
});

await etape('fin de manche à la cible (4 points)', async () => {
  const a = joueurs.admin;
  for (const [cible, attendu] of [[joueurs.ami, 2], [joueurs.ami, 3], [joueurs.invite, 4]]) {
    const t = await tirer(a, cible);
    assert.equal(t.t, 'touche', JSON.stringify(t));
    assert.equal(t.points, attendu);
    await pause(1700);
  }
  for (const x of Object.values(joueurs)) {
    const fin = await x.s.type('fin');
    assert.equal(fin.manche, 1);
    assert.equal(fin.gagnant, a.j);
    assert.equal(fin.raison, 'points');
    assert.equal(fin.classement[0].points, 4);
  }
});

await etape('manche enregistrée dans D1', async () => {
  await pause(300);
  const d = await admin.json(await admin.get(`/api/salons/${salon}`));
  assert.equal(d.salon.manches, 1);
  const m = d.manches[0];
  assert.equal(m.numero, 1);
  assert.equal(m.gagnant, 'Valentin');
  assert.equal(m.raison, 'points');
  assert.deepEqual(m.classement.map(x => x.points), [4, 0, 0]);
});

await etape('manche 2 relancée par n\'importe qui, scores remis à zéro', async () => {
  joueurs.invite.s.envoyer({ t: 'lancer', spawns: SPAWNS });
  for (const x of Object.values(joueurs)) {
    const d = await x.s.type('debut');
    assert.equal(d.manche, 2);
    assert.equal(d.cible, 4);
    assert.equal(d.joueurs.length, 3);
    x.pos = d.joueurs.find(p => p.j === x.j).spawn.slice(0, 3);
  }
  const e = await joueurs.admin.s.attendre(m => m.t === 'etat' && m.manche === 2);
  assert.ok(e.joueurs.every(x => x.points === 0 && x.vies === 3 && !x.elimine));
  clearInterval(boucle);
  for (const x of Object.values(joueurs)) x.s.fermer();
});

await etape('salon persistant : toujours accessible après les manches', async () => {
  assert.equal((await admin.ticket(salon)).rep.status, 200);
  assert.equal((await new Client(BASE).connexionDev(INCONNU)).status, 303, 'membre tant que le salon existe');
});

console.log(`\n${ok} étapes réussies`);
process.exit(0);
