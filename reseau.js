// Salon en ligne du paintball : connexion Google, parties, invitations, liste autorisée (admin), lobby,
// et WebSocket de la partie. Protocole : serveur/PROTOCOLE.md. Le jeu Unity reçoit les messages de partie
// par SendMessage('Reseau', 'Recevoir', json), null remplacés pour JsonUtility (ClientReseau.cs).
(() => {
  'use strict';
  const ADRESSE_EN_LIGNE = 'https://paintball-saint-victor.marseille-tech.workers.dev';
  const COULEURS = ['#1ad9ff', '#ff3b87', '#ffb812', '#70ff45', '#a354ff', '#ff6b1f'];
  const NOMS_COULEURS = ['Cyan', 'Framboise', 'Soleil', 'Citron vert', 'Violet', 'Mandarine'];
  const VERS_JEU = new Set(['bienvenue', 'etat', 'debut', 'ps', 'corr', 'tir', 'touche', 'elimine', 'fin', 'refus']);

  const etat = {
    apparitions: null, couleur: 0, moi: null, csrf: null, partie: null, nomPartie: '', ws: null, j: -1,
    hote: false, salon: null, enJeu: false, ouvert: false, message: '', invitation: null, autorises: null,
    tentatives: 0, ping: null, latences: [], latence: 0, parties: [],
  };
  const partieDemandee = new URLSearchParams(location.search).get('partie');

  // ---------- Interface ----------
  const style = document.createElement('style');
  style.textContent = `
#salon{position:fixed;inset:0;z-index:10;display:none;align-items:center;justify-content:center;background:rgba(11,26,21,.82);
  font:15px system-ui,sans-serif;color:#f4f0e7;-webkit-user-select:text;user-select:text}
#salon.ouvert{display:flex}
#salon .panneau{width:min(760px,94vw);max-height:92vh;overflow:auto;background:#10251f;border:1px solid rgba(173,148,100,.45);
  border-radius:18px;padding:26px 30px;box-shadow:0 20px 60px rgba(0,0,0,.45)}
#salon h2{font:400 34px Georgia,serif;margin:0 0 4px}
#salon h3{font:600 12px system-ui;letter-spacing:.18em;color:#ad9464;margin:22px 0 8px;text-transform:uppercase}
#salon p{margin:6px 0;line-height:1.45;opacity:.9}
#salon .ligne{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:6px 0}
#salon .ligne.espace{justify-content:space-between}
#salon button{font:600 14px system-ui;padding:9px 18px;border-radius:999px;border:1.5px solid rgba(244,240,231,.6);
  background:transparent;color:#f4f0e7;cursor:pointer}
#salon button:hover,#salon button:focus-visible{border-color:#f4f0e7;background:rgba(244,240,231,.08);outline:none}
#salon button.plein{background:#f4f0e7;color:#0b1a15;border-color:#f4f0e7}
#salon button:disabled{opacity:.4;cursor:default}
#salon input{font:15px system-ui;padding:9px 12px;border-radius:10px;border:1px solid rgba(244,240,231,.35);
  background:rgba(255,255,255,.05);color:#f4f0e7;min-width:220px}
#salon ul{list-style:none;padding:0;margin:0}
#salon li{display:flex;align-items:center;gap:10px;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(173,148,100,.2)}
#salon .pastille{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:8px;vertical-align:-2px}
#salon .discret{opacity:.65;font-size:13px}
#salon .alerte{color:#ffb4a8}
#salon .qr{background:#fff;border-radius:10px;padding:8px;width:180px;height:180px}
#salon .lien{font:13px ui-monospace,monospace;word-break:break-all;opacity:.85}`;
  document.head.appendChild(style);
  const fond = document.createElement('div');
  fond.id = 'salon';
  fond.innerHTML = '<div class="panneau" role="dialog" aria-modal="true" aria-label="Jouer en ligne"></div>';
  document.body.appendChild(fond);
  const panneau = fond.firstElementChild;
  // Les touches tapées dans le salon ne vont pas au jeu.
  // Les touches tapées dans le salon ne vont pas au jeu : Unity écoute le clavier sur window et annule
  // l'action par défaut (aucun caractère n'apparaîtrait dans les champs). Écouteurs en capture, posés
  // avant le chargement de Unity, donc appelés avant les siens ; la saisie du jeu est aussi coupée.
  for (const type of ['keydown', 'keyup', 'keypress']) window.addEventListener(type, e => {
    if (!etat.ouvert) return;
    if (type === 'keydown' && e.key === 'Escape' && !etat.salon) fermer();
    e.stopImmediatePropagation();
  }, true);
  const clavierJeu = actif => window.unityInstance?.SendMessage('Reseau', 'Clavier', actif ? '1' : '0');

  const echap = t => String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const bouton = (texte, action, plein = false, actif = true) =>
    `<button data-action="${action}" class="${plein ? 'plein' : ''}" ${actif ? '' : 'disabled'}>${texte}</button>`;
  panneau.addEventListener('click', e => {
    const b = e.target.closest('button[data-action]');
    if (!b || b.disabled) return;
    const [action, valeur] = b.dataset.action.split(':');
    actions[action]?.(valeur, b);
  });
  panneau.addEventListener('submit', e => {
    e.preventDefault();
    const f = e.target;
    actions[f.dataset.action]?.(new FormData(f));
  });

  function afficher() {
    const m = etat.message ? `<p class="alerte">${echap(etat.message)}</p>` : '';
    if (etat.salon) { panneau.innerHTML = vueLobby() + m; return; }
    if (etat.moi === undefined) {
      panneau.innerHTML = `<h2>Jouer en ligne</h2><p>Le jeu à plusieurs se lance depuis son adresse en ligne :</p>
        <p><a href="${ADRESSE_EN_LIGNE}" style="color:#f4f0e7">${ADRESSE_EN_LIGNE.replace('https://', '')}</a></p>
        <div class="ligne">${bouton('Fermer', 'fermer')}</div>${m}`;
      return;
    }
    if (etat.moi === null) {
      panneau.innerHTML = `<h2>Jouer en ligne</h2><p>Connectez-vous avec votre compte Google pour créer une partie ou rejoindre
        celle où l'on vous a invité. Seules les adresses autorisées par l'organisateur peuvent jouer.</p>
        <div class="ligne">${bouton('Se connecter avec Google', 'connexion', true)}${bouton('Fermer', 'fermer')}</div>${m}`;
      return;
    }
    const u = etat.moi;
    let h = `<div class="ligne espace"><h2>Jouer en ligne</h2>${bouton('Fermer', 'fermer')}</div>
      <div class="ligne espace"><span>${echap(u.nom)} <span class="discret">${echap(u.email)}</span></span>${bouton('Se déconnecter', 'deconnexion')}</div>`;
    h += '<h3>Parties</h3>';
    const parties = (etat.parties ?? []).filter(p => p.etat !== 'terminee');
    h += parties.length ? '<ul>' + parties.map(p => `<li><span>${echap(p.nom)} <span class="discret">${p.etat === 'en_cours' ? 'en cours' : 'en attente'}</span></span>
      <span class="ligne">${u.admin ? bouton('Inviter', 'inviter:' + p.id) : ''}${bouton('Rejoindre', 'rejoindre:' + p.id, true)}</span></li>`).join('') + '</ul>'
      : '<p class="discret">Aucune partie ouverte pour vous. Demandez un lien d’invitation à l’organisateur.</p>';
    if (u.admin) {
      h += `<h3>Nouvelle partie</h3><form data-action="creer" class="ligne"><input name="nom" maxlength="40" placeholder="Nom de la partie" required>
        <button class="plein">Créer</button></form>`;
      if (etat.invitation) {
        const i = etat.invitation;
        h += `<h3>Invitation</h3><div class="ligne" style="align-items:flex-start;gap:18px"><img class="qr" src="${echap(i.qr_url)}" alt="QR code du lien d'invitation">
          <div style="flex:1;min-width:220px"><p>Valable 24 h ; toute personne qui l'ouvre est autorisée pour cette partie.</p>
          <p class="lien">${echap(i.lien)}</p><div class="ligne">${bouton('Copier le lien', 'copier', true)}</div></div></div>`;
      }
      h += '<h3>Adresses autorisées</h3>';
      if (etat.autorises) {
        h += '<ul>' + etat.autorises.map(a => `<li><span>${echap(a.email)} ${a.admin ? '<span class="discret">admin</span>' : ''}</span>
          ${a.email === u.email ? '' : bouton('Retirer', 'retirer:' + encodeURIComponent(a.email))}</li>`).join('') + '</ul>';
      } else h += '<p class="discret">Chargement…</p>';
      h += `<form data-action="autoriser" class="ligne" style="margin-top:10px"><input name="email" type="email" placeholder="adresse@gmail.com" required>
        <button>Autoriser</button></form>`;
    }
    panneau.innerHTML = h + m;
  }

  function vueLobby() {
    const s = etat.salon;
    const joueurs = s.joueurs ?? [];
    const moi = joueurs.find(x => x.j === etat.j);
    const enCours = s.phase === 'en_cours';
    let h = `<div class="ligne espace"><h2>${echap(etat.nomPartie || 'Partie')}</h2>${bouton('Quitter', 'quitter')}</div>`;
    h += `<p class="discret">${enCours ? 'Partie en cours.' : `En attente des joueurs · ${joueurs.length} / 8 · victoire à ${Math.floor(3 * Math.max(2, joueurs.length) / 2)} points`}
      ${etat.latence ? ` · latence ${etat.latence} ms` : ''}</p><h3>Joueurs</h3><ul>`;
    h += joueurs.map(x => `<li><span><span class="pastille" style="background:${COULEURS[x.c] ?? '#fff'}"></span>${echap(x.nom)}${x.j === etat.j ? ' <span class="discret">(vous)</span>' : ''}
      ${x.j === s.hote ? ' <span class="discret">· organisateur</span>' : ''}</span><span class="discret">${x.connecte === false ? 'déconnecté' : x.pret ? 'prêt' : ''}</span></li>`).join('');
    h += '</ul>';
    if (!enCours) {
      h += `<h3>Votre couleur</h3><div class="ligne">${COULEURS.map((c, i) => `<button data-action="couleur:${i}" aria-label="${NOMS_COULEURS[i]}"
        style="width:34px;height:34px;padding:0;background:${c};border:${i === etat.couleur ? '3px solid #f4f0e7' : '1.5px solid transparent'}"></button>`).join('')}</div>`;
      h += `<div class="ligne" style="margin-top:18px">${bouton(moi?.pret ? 'Prêt ✓' : 'Je suis prêt', 'pret', !moi?.pret)}`;
      if (etat.j === s.hote) h += bouton('Démarrer la partie', 'demarrer', true, joueurs.length >= 2 && !!etat.apparitions);
      h += '</div>';
      if (etat.j === s.hote && joueurs.length < 2) h += '<p class="discret">Il faut au moins deux joueurs pour démarrer.</p>';
    }
    return h;
  }

  // ---------- HTTP ----------
  async function api(methode, chemin, corps) {
    const entetes = { 'content-type': 'application/json' };
    if (methode !== 'GET' && etat.csrf) entetes['x-csrf'] = etat.csrf;
    const rep = await fetch(chemin, { method: methode, headers: entetes, credentials: 'same-origin', body: corps ? JSON.stringify(corps) : undefined });
    let donnees = null;
    try { donnees = await rep.json(); } catch { donnees = null; }
    return { statut: rep.status, donnees };
  }

  async function actualiser() {
    etat.message = '';
    let r;
    try { r = await api('GET', '/api/moi'); } catch { r = { statut: 0 }; }
    if (r.statut === 401) { etat.moi = null; etat.csrf = null; afficher(); return; }
    if (r.statut !== 200 || !r.donnees?.email) { etat.moi = undefined; afficher(); return; }
    etat.moi = r.donnees; etat.csrf = r.donnees.csrf;
    const p = await api('GET', '/api/parties');
    etat.parties = p.donnees?.parties ?? [];
    afficher();
    if (etat.moi.admin) {
      const a = await api('GET', '/api/autorises');
      etat.autorises = a.donnees?.autorises ?? [];
      afficher();
    }
  }

  const erreur = r => r.donnees?.erreur ?? `Erreur ${r.statut}`;

  const actions = {
    fermer: () => fermer(),
    connexion: () => { location.href = '/auth/google?retour=' + encodeURIComponent(location.pathname + location.search); },
    deconnexion: async () => { await api('POST', '/auth/deconnexion'); etat.invitation = null; etat.autorises = null; await actualiser(); },
    creer: async form => {
      const r = await api('POST', '/api/parties', { nom: String(form.get('nom')).trim() });
      if (r.statut !== 201) { etat.message = erreur(r); afficher(); return; }
      await actions.inviter(r.donnees.id);
      await actualiser();
    },
    inviter: async id => {
      const r = await api('POST', `/api/parties/${id}/invitations`, { duree_min: 1440, auto: true });
      if (r.statut !== 200 && r.statut !== 201) { etat.message = erreur(r); afficher(); return; }
      etat.invitation = r.donnees; afficher();
    },
    copier: async (_, b) => {
      try { await navigator.clipboard.writeText(etat.invitation.lien); b.textContent = 'Lien copié'; }
      catch { etat.message = 'Copie impossible : sélectionnez le lien.'; afficher(); }
    },
    autoriser: async form => {
      const r = await api('POST', '/api/autorises', { email: String(form.get('email')).trim().toLowerCase() });
      if (r.statut !== 200) etat.message = erreur(r);
      await actualiserAutorises();
    },
    retirer: async email => {
      email = decodeURIComponent(email);
      if (!confirm(`Retirer ${email} ? Ses sessions et ses accès seront révoqués.`)) return;
      const r = await api('POST', '/api/autorises/retirer', { email });
      if (r.statut !== 200) etat.message = erreur(r);
      await actualiserAutorises();
    },
    rejoindre: id => rejoindre(id),
    quitter: () => { quitter(); actualiser(); },
    couleur: i => { etat.couleur = Number(i); envoyer(JSON.stringify({ t: 'pret', c: etat.couleur })); afficher(); },
    pret: () => envoyer(JSON.stringify({ t: 'pret', c: etat.couleur })),
    demarrer: () => envoyer(`{"t":"demarrer","spawns":${etat.apparitions}}`),
  };

  async function actualiserAutorises() {
    const a = await api('GET', '/api/autorises');
    etat.autorises = a.donnees?.autorises ?? [];
    afficher();
  }

  // ---------- Partie ----------
  async function rejoindre(id) {
    etat.message = '';
    const info = await api('GET', `/api/parties/${id}`);
    if (info.statut !== 200) { etat.message = erreur(info); afficher(); return; }
    etat.partie = id; etat.nomPartie = info.donnees?.partie?.nom ?? '';
    await connecter();
  }

  async function connecter() {
    const t = await api('POST', `/api/parties/${etat.partie}/ticket`);
    if (t.statut !== 200) { etat.message = erreur(t); etat.salon = null; afficher(); return; }
    etat.hote = false;
    const ws = new WebSocket(t.donnees.ws);
    etat.ws = ws;
    ws.onopen = () => { etat.tentatives = 0; clearInterval(etat.ping); etat.ping = setInterval(() => envoyer(JSON.stringify({ t: 'ping', c: performance.now() })), 1000); };
    ws.onmessage = e => recevoir(e.data);
    ws.onclose = e => fermeture(ws, e.code);
  }

  function recevoir(texte) {
    let m;
    try { m = JSON.parse(texte); } catch { return; }
    switch (m.t) {
      case 'pong': {
        etat.latences.push(performance.now() - m.c);
        if (etat.latences.length > 10) etat.latences.shift();
        etat.latence = Math.round([...etat.latences].sort((a, b) => a - b)[etat.latences.length >> 1]);
        versJeu({ t: 'latence', v: etat.latence, h: m.h });
        return;
      }
      case 'bienvenue': etat.j = m.j; break;
      case 'etat':
        etat.salon = m;
        if (m.phase === 'en_cours' && !etat.enJeu && etat.ouvert) etat.message = 'La partie a commencé sans vous.';
        if (m.phase === 'terminee') etat.enJeu = false;
        if (etat.ouvert) afficher();
        break;
      case 'debut': etat.enJeu = true; fermer(true); break;
      case 'fin': etat.enJeu = false; break;
    }
    if (VERS_JEU.has(m.t)) versJeu(m);
  }

  // JsonUtility ne lit pas null : valeurs de remplacement, objet fin de l'état retiré.
  function versJeu(m) {
    if (m.t === 'etat') { m.hote ??= -1; delete m.fin; }
    for (const k of ['j', 'gagnant', 'cible', 'tireur', 'hote']) if (k in m && m[k] === null) m[k] = -1;
    if ('spawn' in m && !Array.isArray(m.spawn)) m.spawn = [];
    if (Array.isArray(m.joueurs)) for (const x of m.joueurs) if ('spawn' in x && !Array.isArray(x.spawn)) x.spawn = [];
    window.unityInstance?.SendMessage('Reseau', 'Recevoir', JSON.stringify(m));
  }

  function fermeture(ws, code) {
    if (ws !== etat.ws) return;
    clearInterval(etat.ping);
    etat.ws = null;
    const raisons = { 4001: 'Connexion remplacée : la partie est ouverte ailleurs avec ce compte.', 4003: 'Entrée refusée : partie complète ou déjà commencée.', 4008: 'Connexion fermée par le serveur.' };
    if (raisons[code] || !etat.partie) { etat.message = raisons[code] ?? ''; etat.salon = null; etat.partie = null; if (etat.ouvert) afficher(); return; }
    // Coupure : nouveau ticket et nouvelle connexion (le serveur garde la place 30 s en partie).
    if (etat.tentatives++ < 5) setTimeout(() => { if (etat.partie) connecter(); }, 1000 * etat.tentatives);
    else { etat.message = 'Connexion au serveur perdue.'; etat.salon = null; ouvrir(etat.couleur); }
  }

  function envoyer(texte) { if (etat.ws?.readyState === 1) etat.ws.send(texte); }

  function quitter() {
    const ws = etat.ws;
    etat.partie = null; etat.salon = null; etat.enJeu = false; etat.ws = null; etat.j = -1;
    clearInterval(etat.ping);
    if (ws) ws.close(1000);
    if (new URLSearchParams(location.search).has('partie')) history.replaceState(null, '', location.pathname);
  }

  function ouvrir(couleur) {
    if (typeof couleur === 'number') etat.couleur = couleur;
    if (document.pointerLockElement) document.exitPointerLock();
    etat.ouvert = true; fond.classList.add('ouvert');
    clavierJeu(false);
    afficher();
    if (!etat.salon) actualiser();
    setTimeout(() => panneau.querySelector('button')?.focus(), 50);
  }

  function fermer(garder) {
    etat.ouvert = false; fond.classList.remove('ouvert');
    clavierJeu(true);
    if (!garder && etat.salon && !etat.enJeu) quitter();
    document.getElementById('unity-canvas')?.focus();
  }

  window.paintballReseau = {
    ouvrir, envoyer, quitter: () => { quitter(); },
    unityPret: apparitions => {
      etat.apparitions = apparitions;
      // Arrivée par un lien d'invitation : ouvrir le salon et rejoindre la partie.
      if (partieDemandee && !etat.partie) {
        ouvrir(etat.couleur);
        api('GET', '/api/moi').then(r => {
          if (r.statut === 401) { location.href = '/auth/google?retour=' + encodeURIComponent(location.pathname + location.search); return; }
          if (r.statut === 200 && r.donnees?.email) { etat.moi = r.donnees; etat.csrf = r.donnees.csrf; rejoindre(partieDemandee); }
        });
      }
    },
    etat,
  };
})();
