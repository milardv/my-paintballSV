// Outil de charge : P salons de N joueurs simulés (une manche chacun), positions à F Hz, tirs, pings.
// node outils/charge.mjs [--base http://127.0.0.1:8787] [--joueurs 8] [--parties 1] [--hz 30] [--tirs 4] [--duree 30]
// Nécessite la connexion /auth/dev : MODE_DEV=1 sous `wrangler dev`, ou CLE_MESURE=… contre l'environnement de mesure.
//
// Mesures :
// - aller-retour ping/pong (client → DO → client) ;
// - relais : émission d'une position par un bot → réception par un autre bot (même horloge locale) ;
// - débit de messages reçus et envoyés par le DO (compteurs du DO) ;
// - CPU des processus workerd locaux (runtime et proxy de wrangler, lus dans /proc).
import { readFileSync, readdirSync } from 'node:fs';
import { Client, Socket, pause, quantiles } from './client.mjs';

const opt = { base: 'http://127.0.0.1:8787', joueurs: 8, parties: 1, hz: 30, tirs: 4, duree: 30 };
const a = process.argv.slice(2);
for (let i = 0; i < a.length; i += 2) {
  const k = a[i].replace(/^--/, '');
  opt[k] = k === 'base' ? a[i + 1] : Number(a[i + 1]);
}
// En local (MODE_DEV=1) : admin de configuration. Environnement de mesure déployé : CLE_MESURE dans l'environnement.
const CLE_MESURE = process.env.CLE_MESURE;
const ADMIN = CLE_MESURE ? 'admin@charge.test' : process.env.ADMIN_EMAIL ?? 'admin@exemple.fr';
if (CLE_MESURE) Client.prototype.entetesCommuns = { 'x-cle-mesure': CLE_MESURE };
const ws = opt.base.replace(/^http/, 'ws');

/** Temps CPU (s) de chaque processus workerd local ; le proxy de wrangler écoute sur le port public. */
function cpuWorkerd() {
  const r = {};
  for (const pid of readdirSync('/proc').filter(d => /^\d+$/.test(d))) {
    try {
      if (readFileSync(`/proc/${pid}/comm`, 'utf8').trim() !== 'workerd') continue;
      const champs = readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].split(' ');
      const proxy = readFileSync(`/proc/${pid}/cmdline`, 'utf8').includes(`entry=${new URL(opt.base).host}`);
      r[proxy ? 'proxy' : 'runtime'] = (r[proxy ? 'proxy' : 'runtime'] ?? 0) + (Number(champs[11]) + Number(champs[12])) / 100;
    } catch { /* processus disparu */ }
  }
  return r;
}

const admin = new Client(opt.base);
if ((await admin.connexionDev(ADMIN)).status !== 303) throw new Error('connexion admin impossible (MODE_DEV=1 ?)');

const rtt = [], relais = [];
let recusTotal = 0, envoyesTotal = 0, refus = 0;
const parties = [];

for (let p = 0; p < opt.parties; p++) {
  const salon = await admin.json(await admin.post('/api/salons', { nom: `Charge ${p}` }));
  const id = salon.id;
  const jeton = salon.lien.split('/s/')[1];
  const bots = [];
  for (let b = 0; b < opt.joueurs; b++) {
    const c = b === 0 ? admin : new Client(opt.base);
    if (b > 0 && (await c.connexionDev(`bot${b}-${id}@charge.test`, `Bot ${b}`, jeton)).status !== 303) throw new Error('connexion bot');
    const { corps } = await c.ticket(id);
    const s = await Socket.ouvrir(corps.ws.replace(/^wss?:\/\/[^/]+/, ws));
    const bienvenue = await s.type('bienvenue', 30000);
    bots.push({ s, j: bienvenue.j, pos: [0, 0, 0], q: 0, envois: new Map(), tir: 0 });
  }
  await pause(200);
  bots[0].s.envoyer({ t: 'lancer', spawns: Array.from({ length: 16 }, (_, i) => [i * 6, 0, (i % 4) * 6, 0]) });
  for (const b of bots) {
    const d = await b.s.type('debut', 30000);
    b.pos = d.joueurs.find(x => x.j === b.j).spawn.slice(0, 3);
  }
  parties.push({ id, bots });
}

// Mesures sur les messages reçus.
const parJ = new Map();
for (const { bots } of parties) {
  for (const b of bots) {
    parJ.set(b, new Map(bots.map(x => [x.j, x])));
    b.s.recus.length = 0;
    b.s.surMessage = m => {
      recusTotal++;
      const t = performance.now();
      if (m.t === 'pong') rtt.push(t - m.c);
      else if (m.t === 'ps') {
        for (const x of m.l) {
          if (x.j === b.j) continue;
          const t0 = parJ.get(b).get(x.j)?.envois.get(x.q);
          if (t0 !== undefined) relais.push(t - t0);
        }
      } else if (m.t === 'refus') refus++;
      b.s.recus.length = 0;
    };
  }
}

const cpu0 = cpuWorkerd();
const debut = performance.now();
const minuteries = [];
for (const { bots } of parties) {
  for (const b of bots) {
    const phase = Math.random() * (1000 / opt.hz);
    const angle = Math.random() * Math.PI * 2;
    minuteries.push(setTimeout(() => minuteries.push(setInterval(() => {
      const t = performance.now();
      b.q++;
      // Marche circulaire lente (3 m/s) autour du point d'apparition.
      const k = (t - debut) / 1000;
      const p = [b.pos[0] + Math.cos(angle + k) * 3, 0, b.pos[2] + Math.sin(angle + k) * 3];
      b.envois.set(b.q, t);
      if (b.envois.size > 200) b.envois.delete(b.q - 200);
      b.s.envoyer({ t: 'p', q: b.q, p, r: [k * 30 % 360, 0], v: [0, 0, 0] });
      envoyesTotal++;
    }, 1000 / opt.hz)), phase));
    minuteries.push(setInterval(() => { b.s.envoyer({ t: 'ping', c: performance.now() }); envoyesTotal++; }, 500));
    if (opt.tirs > 0) {
      minuteries.push(setInterval(() => {
        b.s.envoyer({ t: 'tir', id: ++b.tir, o: [b.pos[0], 1.5, b.pos[2]], d: [0, 0.05, 0.9987] });
        envoyesTotal++;
      }, 1000 / opt.tirs));
    }
  }
}

await pause(opt.duree * 1000);
for (const m of minuteries) { clearInterval(m); clearTimeout(m); }
const ecoule = (performance.now() - debut) / 1000;
const cpu1 = cpuWorkerd();

// Compteurs côté DO (demandés par l'hôte de chaque partie).
let doRecus = 0, doEnvoyes = 0;
for (const { bots } of parties) {
  bots[0].s.surMessage = null;
  bots[0].s.envoyer({ t: 'stats' });
  const st = await bots[0].s.type('stats', 30000);
  doRecus += st.recus;
  doEnvoyes += st.envoyes;
}
for (const { bots } of parties) for (const b of bots) b.s.fermer();

const r = quantiles(rtt), l = quantiles(relais);
const f = x => x.toFixed(1);
const resultat = {
  date: new Date().toISOString(), base: opt.base, parties: opt.parties, joueurs: opt.joueurs, hz: opt.hz, tirs: opt.tirs,
  duree_s: Number(ecoule.toFixed(1)),
  rtt_ms: { n: r.n, p50: f(r.p50), p95: f(r.p95), p99: f(r.p99), max: f(r.max) },
  relais_ms: { n: l.n, p50: f(l.p50), p95: f(l.p95), p99: f(l.p99), max: f(l.max) },
  do_recus_par_s: Math.round(doRecus / ecoule), do_envoyes_par_s: Math.round(doEnvoyes / ecoule),
  clients_recus_par_s: Math.round(recusTotal / ecoule), refus,
  cpu_pct: Object.fromEntries(Object.keys(cpu1).map(k => [k, Number((100 * (cpu1[k] - (cpu0[k] ?? 0)) / ecoule).toFixed(1))])),
};
resultat.cpu_runtime_ms_par_message = resultat.cpu_pct.runtime === undefined ? null
  : Number((resultat.cpu_pct.runtime * 10 / (doRecus / ecoule)).toFixed(2));
console.log(JSON.stringify(resultat, null, 2));
console.log(`| ${opt.parties} × ${opt.joueurs} | ${opt.hz} Hz | ${r.p50.toFixed(1)} / ${r.p95.toFixed(1)} | ${l.p50.toFixed(1)} / ${l.p95.toFixed(1)} | ${resultat.do_recus_par_s} / ${resultat.do_envoyes_par_s} | ${resultat.cpu_pct.runtime ?? '–'} % | ${resultat.cpu_pct.proxy ?? '–'} % | ${resultat.cpu_runtime_ms_par_message ?? '–'} |`);
process.exit(0);
