// Prépare le build WebGL pour les Static Assets du Worker, dans serveur/jeu/ (envoyé par `wrangler deploy`).
// node outils/preparer-jeu.mjs [dossier]   (dossier par défaut : ../publication, lu seulement)
//
// Les Static Assets limitent chaque fichier à 25 Mio : chaque fichier est découpé en morceaux de 20 Mio,
// que le Worker recolle à la volée (manifeste.json). Les fichiers de Build/ sont servis sous
// Build/<empreinte>/ avec un cache privé d'un an (immutable) ; index.html, réécrit pour pointer vers ces
// chemins, est revalidé à chaque visite (no-cache).
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ici = dirname(fileURLToPath(import.meta.url));
const source = resolve(process.argv[2] ?? join(ici, '../../publication'));
const cible = join(ici, '../jeu');
const MORCEAU = 20 * 1024 * 1024;

const TYPES = {
  html: 'text/html; charset=utf-8', js: 'application/javascript', wasm: 'application/wasm', data: 'application/octet-stream',
  png: 'image/png', json: 'application/json', ico: 'image/x-icon', css: 'text/css', svg: 'image/svg+xml',
};
const typeDe = nom => TYPES[nom.replace(/\.unityweb$/, '').split('.').pop()] ?? 'application/octet-stream';
const empreinteDe = octets => createHash('sha256').update(octets).digest('hex').slice(0, 16);

function encodageDe(octets) {
  if (octets[0] === 0x1f && octets[1] === 0x8b) return 'gzip';
  if (octets.subarray(0, 128).toString('latin1').includes('UnityWeb Compressed Content (brotli)')) return 'br';
  return null;
}

rmSync(cible, { recursive: true, force: true });
mkdirSync(join(cible, 'm'), { recursive: true });
const manifeste = {};

/** Écrit les morceaux sous m/<empreinte>.<n>.bin (noms opaques : rien n'est servi directement). */
function ajouter(cle, octets, { type, encodage = null, cache }) {
  const empreinte = empreinteDe(octets);
  const morceaux = [];
  for (let i = 0, n = 0; i < Math.max(octets.length, 1); i += MORCEAU, n++) {
    const nom = `m/${empreinte}.${n}.bin`;
    writeFileSync(join(cible, nom), octets.subarray(i, i + MORCEAU));
    morceaux.push(nom);
  }
  manifeste[cle] = { type, encodage, cache, empreinte, taille: octets.length, morceaux };
  console.log(`${cle} (${(octets.length / 1e6).toFixed(1)} Mo, ${morceaux.length} morceau${morceaux.length > 1 ? 'x' : ''}${encodage ? ', ' + encodage : ''})`);
}

// Fichiers réservés aux comptes connectés : cache du navigateur seulement (private).
const LONG = 'private, max-age=31536000, immutable';
let index = readFileSync(join(source, 'index.html'), 'utf8');
for (const nom of readdirSync(join(source, 'Build'))) {
  const octets = readFileSync(join(source, 'Build', nom));
  const cle = `Build/${empreinteDe(octets).slice(0, 12)}/${nom}`;
  if (!index.includes(`Build/${nom}`)) console.warn(`attention : Build/${nom} n'est pas référencé par index.html`);
  index = index.replaceAll(`Build/${nom}`, cle);
  ajouter(cle, octets, { type: typeDe(nom), encodage: nom.endsWith('.unityweb') ? encodageDe(octets) : null, cache: LONG });
}
for (const nom of readdirSync(source)) {
  const chemin = join(source, nom);
  if (nom === 'index.html' || !statSync(chemin).isFile()) continue;
  // Hors Build/, les noms ne changent pas d'une version à l'autre (reseau.js…) : revalidés à chaque visite (ETag, 304).
  ajouter(nom, readFileSync(chemin), { type: typeDe(nom), cache: 'private, no-cache' });
}
ajouter('index.html', Buffer.from(index), { type: TYPES.html, cache: 'private, no-cache' });
writeFileSync(join(cible, 'manifeste.json'), JSON.stringify(manifeste));
console.log(`${Object.keys(manifeste).length} fichiers prêts dans serveur/jeu/ ; envoyés au prochain \`wrangler deploy\`.`);
