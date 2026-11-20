// Client de test commun (tests d'intégration et outil de charge) : HTTP avec cookies, WebSocket, balistique.

export class Client {
  constructor(base) {
    this.base = base;
    this.cookies = new Map();
    this.csrf = null;
  }

  enregistrer(rep) {
    for (const c of rep.headers.getSetCookie()) {
      const [paire, ...attrs] = c.split(';');
      const [nom, ...v] = paire.split('=');
      const valeur = v.join('=');
      if (attrs.some(a => a.trim().toLowerCase() === 'max-age=0') || valeur === '') this.cookies.delete(nom.trim());
      else this.cookies.set(nom.trim(), valeur);
    }
  }

  entetes(extra = {}) {
    const h = { ...(this.entetesCommuns ?? {}), ...extra };
    if (this.cookies.size) h.cookie = [...this.cookies].map(([k, v]) => `${k}=${v}`).join('; ');
    return h;
  }

  async get(chemin, extra) {
    const rep = await fetch(this.base + chemin, { headers: this.entetes(extra), redirect: 'manual' });
    this.enregistrer(rep);
    return rep;
  }

  async post(chemin, corps = {}, { csrf = true, extra = {} } = {}) {
    const h = this.entetes({ 'content-type': 'application/json', ...(csrf && this.csrf ? { 'x-csrf': this.csrf } : {}), ...extra });
    const rep = await fetch(this.base + chemin, { method: 'POST', headers: h, body: JSON.stringify(corps), redirect: 'manual' });
    this.enregistrer(rep);
    return rep;
  }

  async json(rep) {
    const t = await rep.text();
    try { return JSON.parse(t); } catch { return { brut: t }; }
  }

  /** Connexion du mode dev (MODE_DEV=1, hôte local seulement). */
  async connexionDev(email, nom, lien) {
    const q = new URLSearchParams({ email, nom: nom ?? email.split('@')[0] });
    if (lien) q.set('lien', lien);
    const rep = await this.get('/auth/dev?' + q);
    if (rep.status === 303) {
      const moi = await this.json(await this.get('/api/moi'));
      this.csrf = moi.csrf;
      this.moi = moi;
    }
    return rep;
  }

  async ticket(salon) {
    const rep = await this.post(`/api/salons/${salon}/ticket`);
    return { rep, corps: await this.json(rep) };
  }
}

/** WebSocket avec file de messages et attente par prédicat. */
export class Socket {
  static ouvrir(url, options) {
    return new Promise((ok, ko) => {
      const s = new Socket(new WebSocket(url, options));
      s.ws.addEventListener('open', () => ok(s), { once: true });
      s.ws.addEventListener('error', e => ko(new Error('WebSocket : ' + (e.message ?? 'erreur'))), { once: true });
    });
  }

  constructor(ws) {
    this.ws = ws;
    this.recus = [];
    this.attentes = [];
    this.surMessage = null;
    this.ferme = null;
    ws.addEventListener('message', e => {
      const m = JSON.parse(e.data);
      if (this.surMessage) this.surMessage(m);
      const i = this.attentes.findIndex(a => a.pred(m));
      if (i >= 0) {
        const [a] = this.attentes.splice(i, 1);
        clearTimeout(a.minuterie);
        a.ok(m);
      } else this.recus.push(m);
    });
    ws.addEventListener('close', e => { this.ferme = { code: e.code, raison: e.reason }; });
  }

  envoyer(m) { this.ws.send(JSON.stringify(m)); }

  attendre(pred, ms = 5000) {
    const i = this.recus.findIndex(pred);
    if (i >= 0) return Promise.resolve(this.recus.splice(i, 1)[0]);
    return new Promise((ok, ko) => {
      const a = { pred, ok };
      a.minuterie = setTimeout(() => {
        this.attentes.splice(this.attentes.indexOf(a), 1);
        ko(new Error('délai dépassé : ' + pred.toString()));
      }, ms);
      this.attentes.push(a);
    });
  }

  type(t, ms) { return this.attendre(m => m.t === t, ms); }

  fermer() { this.ws.close(); }
}

// Même modèle que BalistiquePaintball.cs et src/balistique.rs.
const K = 0.5 * 1.225 * 0.47 * Math.PI * 0.017272 ** 2 / (4 * 0.0032);
const DT = 1 / 240;
export const V0 = 85.344;
const acc = v => { const m = Math.hypot(...v); return [-K * m * v[0], -9.81 - K * m * v[1], -K * m * v[2]]; };
const ajoute = (a, b, s) => [a[0] + b[0] * s, a[1] + b[1] * s, a[2] + b[2] * s];

/** Visée directe de o vers c : direction, temps de vol et point d'impact au plus près de c. */
export function viser(o, c) {
  const d0 = [c[0] - o[0], c[1] - o[1], c[2] - o[2]];
  const n = Math.hypot(...d0);
  const d = d0.map(x => x / n);
  let p = o, v = d.map(x => x * V0), t = 0, meilleur = { dist: Infinity };
  while (t < 3) {
    const m = ajoute(v, acc(v), DT / 2);
    const suivant = ajoute(p, m, DT);
    v = ajoute(v, acc(m), DT);
    t += DT;
    const dist = Math.hypot(suivant[0] - c[0], suivant[1] - c[1], suivant[2] - c[2]);
    if (dist < meilleur.dist) meilleur = { dist, t, pt: suivant };
    else break;
    p = suivant;
  }
  return { d, t: meilleur.t, pt: meilleur.pt };
}

export const pause = ms => new Promise(r => setTimeout(r, ms));

export function quantiles(valeurs) {
  const v = [...valeurs].sort((a, b) => a - b);
  const q = p => v.length ? v[Math.min(v.length - 1, Math.floor(p * v.length))] : NaN;
  return { n: v.length, p50: q(0.5), p95: q(0.95), p99: q(0.99), max: v.at(-1) };
}
