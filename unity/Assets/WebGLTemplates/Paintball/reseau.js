// Jeu en ligne du paintball : connexion Google (ou invité par lien de salon), salons, liens et QR codes,
// liste autorisée (admin), salon (pseudo, couleur, manches) et WebSocket. Protocole : serveur/PROTOCOLE.md. Le jeu Unity reçoit les messages de partie
// par SendMessage('Reseau', 'Recevoir', json), null remplacés pour JsonUtility (ClientReseau.cs).
(() => {
  'use strict';
  const ADRESSE_EN_LIGNE = 'https://paintball-saint-victor.marseille-tech.workers.dev';
  const COULEURS = ['#1ad9ff', '#ff3b87', '#ffb812', '#70ff45', '#a354ff', '#ff6b1f'];
  const NOMS_COULEURS = ['Cyan', 'Framboise', 'Soleil', 'Citron vert', 'Violet', 'Mandarine'];
  const VERS_JEU = new Set(['bienvenue', 'etat', 'debut', 'entree', 'ps', 'corr', 'tir', 'touche', 'elimine', 'fin', 'refus']);

  const etat = {
    apparitions: null, couleur: 0, moi: null, csrf: null, salonId: null, nomSalon: '', ws: null, j: -1,
    salon: null, enJeu: false, ouvert: false, message: '', lien: null, autorises: null,
    tentatives: 0, ping: null, latences: [], latence: 0, salons: [], pseudo: '', vies: 3, viesChoisies: (() => { try { return Number(localStorage.getItem('paintballVies')) || 3; } catch (e) { return 3; } })(),
  };
  const salonDemande = new URLSearchParams(location.search).get('salon');

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
#salon .qr.grand{width:min(360px,70vw);height:min(360px,70vw);padding:14px}
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
    if (etat.salon) { panneau.innerHTML = vueSalon() + m; return; }
    if (etat.moi === undefined) {
      panneau.innerHTML = `<h2>Jouer en ligne</h2><p>Le jeu à plusieurs se lance depuis son adresse en ligne :</p>
        <p><a href="${ADRESSE_EN_LIGNE}" style="color:#f4f0e7">${ADRESSE_EN_LIGNE.replace('https://', '')}</a></p>
        <div class="ligne">${bouton('Fermer', 'fermer')}</div>${m}`;
      return;
    }
    if (etat.moi === null && salonDemande) {
      panneau.innerHTML = `<h2>Jouer en ligne</h2><p>Lien expiré, demandez le nouveau lien à l'organisateur.</p>
        <div class="ligne">${bouton('Fermer', 'fermer')}</div>${m}`;
      return;
    }
    if (etat.moi === null) {
      panneau.innerHTML = `<h2>Jouer en ligne</h2><p>Votre session a expiré. Reconnectez-vous avec votre compte Google, ou demandez
        un nouveau lien de salon à l'organisateur.</p>
        <div class="ligne">${bouton('Se connecter avec Google', 'connexion', true)}${bouton('Fermer', 'fermer')}</div>${m}`;
      return;
    }
    const u = etat.moi;
    // QR code d'un salon en grand (admin) : à montrer sur un écran pour que chacun le scanne.
    if (etat.qr && u.admin) {
      const q = etat.qr;
      panneau.innerHTML = `<div class="ligne espace"><h2>${echap(q.nom)}</h2>${bouton('Retour', 'qrfermer')}</div>
        <p>Scannez ce QR code pour entrer dans le salon, sans compte Google.</p>
        <div style="display:flex;justify-content:center;margin:14px 0"><img class="qr grand" src="/api/salons/${encodeURIComponent(q.id)}/qr.svg?${Date.now()}" alt="QR code du lien du salon ${echap(q.nom)}"></div>
        <p class="lien" style="text-align:center">${echap(q.lien ?? '')}</p>
        <div class="ligne" style="justify-content:center">${q.lien ? bouton('Copier le lien', 'copier', true) : ''}${bouton('Entrer', 'rejoindre:' + q.id)}</div>`;
      return;
    }
    let h = `<div class="ligne espace"><h2>Jouer en ligne</h2>${bouton('Fermer', 'fermer')}</div>
      <div class="ligne espace"><span>${echap(u.invite ? 'Invité' : u.nom)} ${u.email ? `<span class="discret">${echap(u.email)}</span>` : ''}</span>
      ${u.invite ? '' : bouton('Se déconnecter', 'deconnexion')}</div>`;
    h += '<h3>Salons</h3>';
    const salons = etat.salons ?? [];
    h += salons.length ? '<ul>' + salons.map(x => `<li><span>${echap(x.nom)}${x.membres != null ? ` <span class="discret">${x.membres} membre${x.membres > 1 ? 's' : ''} · ${x.manches ?? 0} manche${(x.manches ?? 0) > 1 ? 's' : ''}</span>` : ''}</span>
      <span class="ligne">${u.admin ? bouton('QR code', 'qr:' + x.id) + bouton('Lien', 'lien:' + x.id) : ''}${bouton('Entrer', 'rejoindre:' + x.id, true)}</span></li>`).join('') + '</ul>'
      : '<p class="discret">Aucun salon pour vous. Ouvrez le lien que l’organisateur vous a envoyé.</p>';
    if (u.admin) {
      h += `<h3>Nouveau salon</h3><form data-action="creer" class="ligne"><input name="nom" maxlength="60" placeholder="Nom du salon" required>
        <button class="plein">Créer</button></form>`;
      if (etat.lien) {
        const l = etat.lien;
        h += `<h3>Lien du salon « ${echap(l.nom)} »</h3><div class="ligne" style="align-items:flex-start;gap:18px">
          <img class="qr" src="/api/salons/${encodeURIComponent(l.id)}/qr.svg?${Date.now()}" alt="QR code du lien du salon">
          <div style="flex:1;min-width:220px"><p>Toute personne qui ouvre ce lien entre dans le salon, sans compte Google.</p>
          <p class="lien">${echap(l.lien)}</p><div class="ligne">${bouton('Copier le lien', 'copier', true)}${bouton('Nouveau lien', 'renouveler:' + l.id)}${bouton('Supprimer le salon', 'supprimer:' + l.id)}</div></div></div>`;
      }
      h += '<h3>Adresses autorisées</h3>';
      if (etat.autorises) {
        h += '<ul>' + etat.autorises.map(a => `<li><span>${echap(a.email)}</span>
          ${a.email === u.email ? '' : bouton('Retirer', 'retirer:' + encodeURIComponent(a.email))}</li>`).join('') + '</ul>';
      } else h += '<p class="discret">Chargement…</p>';
      h += `<form data-action="autoriser" class="ligne" style="margin-top:10px"><input name="email" type="email" placeholder="adresse@gmail.com" required>
        <button>Autoriser</button></form>`;
    }
    panneau.innerHTML = h + m;
  }

  function vueSalon() {
    const s = etat.salon;
    const joueurs = s.joueurs ?? [];
    const moi = joueurs.find(x => x.j === etat.j);
    const presents = joueurs.filter(x => x.connecte !== false).length;
    const enCours = s.phase === 'en_cours';
    let h = `<div class="ligne espace"><h2>${echap(etat.nomSalon || 'Salon')}</h2>${bouton('Quitter', 'quitter')}</div>`;
    h += `<p class="discret">${enCours ? `Manche ${s.manche} en cours · victoire à ${s.cible} points` : s.phase === 'fin' ? `Manche ${s.manche} terminée` : 'En attente des joueurs'}
      · ${presents} présent${presents > 1 ? 's' : ''}${etat.latence ? ` · latence ${etat.latence} ms` : ''}</p><h3>Joueurs</h3><ul>`;
    h += joueurs.map(x => `<li><span><span class="pastille" style="background:${COULEURS[x.c] ?? '#fff'}"></span>${echap(x.pseudo)}${x.j === etat.j ? ' <span class="discret">(vous)</span>' : ''}</span>
      <span class="discret">${x.connecte === false ? 'déconnecté' : enCours ? (x.en_jeu ? (x.elimine ? 'éliminé' : `${x.vies} vie${x.vies > 1 ? 's' : ''} · ${x.points} pt${x.points > 1 ? 's' : ''}`) : 'spectateur') : ''}</span></li>`).join('');
    h += '</ul>';
    h += `<h3>Votre pseudo et votre couleur</h3><form data-action="pseudo" class="ligne"><input name="pseudo" maxlength="16" minlength="2" value="${echap(moi?.pseudo ?? etat.pseudo)}" required>
      <button>Changer</button></form><div class="ligne">${COULEURS.map((c, i) => `<button data-action="couleur:${i}" aria-label="${NOMS_COULEURS[i]}"
      style="width:34px;height:34px;padding:0;background:${c};border:${i === (moi?.c ?? etat.couleur) ? '3px solid #f4f0e7' : '1.5px solid transparent'}"></button>`).join('')}</div>`;
    h += '<div class="ligne" style="margin-top:18px">';
    // Vies de la prochaine manche : 1, 2, 3, 5 ou 10 (un clic passe au choix suivant).
    if (!enCours) h += bouton(`${etat.viesChoisies} vie${etat.viesChoisies > 1 ? 's' : ''}`, 'vies');
    if (!enCours) h += bouton(s.phase === 'fin' ? 'Relancer une manche' : 'Lancer la manche', 'lancer', true, presents >= 1 && !!etat.apparitions);
    else if (moi && !moi.en_jeu) h += bouton('Entrer dans la manche', 'entrer', true);
    else if (moi?.en_jeu && !moi.elimine) h += bouton('Retour au jeu', 'fermer', true);
    h += '</div>';
    if (!enCours && presents < 2) h += '<p class="discret">Seul, vous pouvez lancer la manche : les autres pourront y entrer en cours.</p>';
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

  async function lireMoi() {
    let r;
    try { r = await api('GET', '/api/moi'); } catch { r = { statut: 0 }; }
    if (r.statut === 401) { etat.moi = null; etat.csrf = null; return false; }
    if (r.statut !== 200 || !r.donnees?.csrf) { etat.moi = undefined; return false; }
    etat.moi = r.donnees; etat.csrf = r.donnees.csrf;
    return true;
  }

  async function actualiser() {
    etat.message = '';
    if (!await lireMoi()) { afficher(); return; }
    const r = await api('GET', '/api/salons');
    etat.salons = r.donnees?.salons ?? [];
    afficher();
    if (etat.moi.admin) await actualiserAutorises();
  }

  async function actualiserAutorises() {
    const a = await api('GET', '/api/autorises');
    etat.autorises = a.donnees?.autorises ?? [];
    afficher();
  }

  const erreur = r => r.donnees?.erreur ?? `Erreur ${r.statut}`;

  const actions = {
    fermer: () => fermer(true),
    connexion: () => { location.href = '/auth/google?retour=' + encodeURIComponent(location.pathname + location.search); },
    deconnexion: async () => { await api('POST', '/auth/deconnexion'); etat.lien = null; etat.autorises = null; await actualiser(); },
    creer: async form => {
      const r = await api('POST', '/api/salons', { nom: String(form.get('nom')).trim() });
      if (r.statut !== 200 && r.statut !== 201) { etat.message = erreur(r); afficher(); return; }
      etat.lien = { id: r.donnees.id, nom: r.donnees.nom, lien: r.donnees.lien };
      await actualiser();
    },
    qr: id => { const x = etat.salons.find(y => y.id === id); if (x) { etat.qr = { id, nom: x.nom, lien: x.lien }; etat.lien = { id, nom: x.nom, lien: x.lien }; afficher(); } },
    qrfermer: () => { etat.qr = null; afficher(); },
    lien: id => { const x = etat.salons.find(y => y.id === id); if (x) { etat.lien = { id, nom: x.nom, lien: x.lien }; afficher(); } },
    renouveler: async id => {
      if (!confirm('Créer un nouveau lien ? L’ancien ne fonctionnera plus et les invités entrés par lui seront exclus.')) return;
      const r = await api('POST', `/api/salons/${id}/lien`);
      if (r.statut !== 200) { etat.message = erreur(r); afficher(); return; }
      etat.lien = { ...etat.lien, lien: r.donnees.lien }; await actualiser();
    },
    supprimer: async id => {
      if (!confirm('Supprimer ce salon ? Son lien ne fonctionnera plus et ses membres en seront retirés.')) return;
      const r = await api('POST', `/api/salons/${id}/supprimer`);
      if (r.statut !== 200) { etat.message = erreur(r); afficher(); return; }
      etat.lien = null; await actualiser();
    },
    copier: async (_, b) => {
      try { await navigator.clipboard.writeText(etat.lien.lien); b.textContent = 'Lien copié'; }
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
    rejoindre: id => { etat.qr = null; rejoindre(id); },
    quitter: () => { quitter(); actualiser(); },
    pseudo: form => { etat.message = ''; envoyer(JSON.stringify({ t: 'profil', pseudo: String(form.get('pseudo')).trim() })); },
    couleur: i => { etat.couleur = Number(i); envoyer(JSON.stringify({ t: 'profil', c: etat.couleur })); },
    lancer: () => envoyer(`{"t":"lancer","spawns":${etat.apparitions},"vies":${etat.viesChoisies}}`),
    vies: () => {
      const choix = [1, 2, 3, 5, 10];
      etat.viesChoisies = choix[(choix.indexOf(etat.viesChoisies) + 1) % choix.length];
      try { localStorage.setItem('paintballVies', String(etat.viesChoisies)); } catch (e) { /* stockage indisponible */ }
      afficher();
    },
    entrer: () => envoyer('{"t":"entrer"}'),
  };

  // ---------- Salon ----------
  async function rejoindre(id) {
    etat.message = '';
    if (!etat.csrf && !await lireMoi()) { afficher(); return; }
    const info = await api('GET', `/api/salons/${id}`);
    if (info.statut !== 200) { etat.message = erreur(info); afficher(); return; }
    etat.salonId = id; etat.nomSalon = info.donnees?.salon?.nom ?? '';
    await connecter();
  }

  async function connecter() {
    const t = await api('POST', `/api/salons/${etat.salonId}/ticket`);
    if (t.statut !== 200) { etat.message = erreur(t); etat.salon = null; afficher(); return; }
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
      case 'bienvenue':
        etat.j = m.j; etat.pseudo = m.pseudo ?? ''; if (typeof m.c === 'number') etat.couleur = m.c;
        if (m.salon?.nom) etat.nomSalon = m.salon.nom;
        if (etat.ouvert) afficher();
        versJeu(m);
        // Reconnexion en pleine manche : reprendre sa place.
        if (m.en_jeu && Array.isArray(m.spawn) && m.spawn.length >= 4) entrerEnJeu(m.spawn, etat.salon?.cible ?? -1);
        return;
      case 'etat':
        etat.salon = m; etat.vies = m.vies ?? etat.vies;
        if (m.phase !== 'en_cours') etat.enJeu = false;
        if (etat.ouvert) afficher();
        break;
      case 'debut': {
        const place = (m.joueurs ?? []).find(x => x.j === etat.j);
        if (!place) return; // spectateur : il peut entrer depuis le salon
        etat.enJeu = true; fermer(true);
        break;
      }
      case 'entree':
        if (m.j === etat.j) { entrerEnJeu(m.spawn, m.cible); return; }
        break;
      case 'fin': etat.enJeu = false; break;
      case 'refus':
        if (etat.ouvert && ['profil', 'lancer', 'entrer'].includes(m.ref)) { etat.message = m.raison; afficher(); }
        break;
      case 'fermeture': etat.codeFermeture = m.code; return;
    }
    if (VERS_JEU.has(m.t)) versJeu(m);
  }

  // Entrée en cours de manche (ou retour) : le jeu démarre avec les joueurs déjà en jeu, sa propre place.
  function entrerEnJeu(spawn, cible) {
    const autres = (etat.salon?.joueurs ?? []).filter(x => x.en_jeu && x.j !== etat.j).map(x => ({ j: x.j, spawn: [] }));
    etat.enJeu = true; fermer(true);
    versJeu({ t: 'debut', cible, vies: etat.vies, joueurs: [{ j: etat.j, spawn }, ...autres] });
  }

  // Pour JsonUtility : pas de null (valeurs de remplacement), objet fin de l'état retiré, pseudo recopié en nom.
  function versJeu(m) {
    if (m.t === 'etat') delete m.fin;
    for (const k of ['j', 'gagnant', 'cible', 'tireur', 'hote']) if (k in m && m[k] === null) m[k] = -1;
    for (const k of ['spawn', 'o', 'pt']) if (k in m && !Array.isArray(m[k])) m[k] = [];
    for (const liste of [m.joueurs, m.classement]) if (Array.isArray(liste)) for (const x of liste) {
      if ('spawn' in x && !Array.isArray(x.spawn)) x.spawn = [];
      if (x.pseudo != null) x.nom = x.pseudo;
    }
    window.unityInstance?.SendMessage('Reseau', 'Recevoir', JSON.stringify(m));
  }

  function fermeture(ws, code) {
    if (ws !== etat.ws) return;
    clearInterval(etat.ping);
    etat.ws = null;
    code = etat.codeFermeture ?? code; etat.codeFermeture = null;
    const raisons = {
      4001: 'Connexion remplacée : le salon est ouvert ailleurs avec ce compte.', 4003: 'Salon plein.',
      4004: 'Ce salon a été supprimé.', 4005: 'Le lien du salon a été renouvelé : demandez le nouveau lien à l’organisateur.',
      4008: 'Connexion fermée par le serveur.',
    };
    if (raisons[code] || !etat.salonId) {
      etat.message = raisons[code] ?? ''; etat.salon = null; etat.salonId = null; etat.enJeu = false;
      versJeu({ t: 'fermeture' }); ouvrir(etat.couleur); return;
    }
    // Coupure : nouveau ticket et nouvelle connexion (la place est gardée 30 s pendant une manche).
    if (etat.tentatives++ < 5) setTimeout(() => { if (etat.salonId) connecter(); }, 1000 * etat.tentatives);
    else { etat.message = 'Connexion au serveur perdue.'; etat.salon = null; etat.salonId = null; ouvrir(etat.couleur); }
  }

  function envoyer(texte) { if (etat.ws?.readyState === 1) etat.ws.send(texte); }

  function quitter() {
    const ws = etat.ws;
    etat.salonId = null; etat.salon = null; etat.enJeu = false; etat.ws = null; etat.j = -1;
    clearInterval(etat.ping);
    if (ws) ws.close(1000);
    if (new URLSearchParams(location.search).has('salon')) history.replaceState(null, '', location.pathname);
  }

  function ouvrir(couleur) {
    if (typeof couleur === 'number' && !etat.salon) etat.couleur = couleur;
    if (document.pointerLockElement) document.exitPointerLock();
    etat.ouvert = true; fond.classList.add('ouvert');
    clavierJeu(false);
    afficher();
    if (!etat.salon) actualiser();
    setTimeout(() => panneau.querySelector('button')?.focus(), 50);
  }

  // garder : laisser la connexion ouverte (retour au jeu) ; sinon, hors manche, quitter le salon.
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
      // Arrivée par un lien de salon (/s/<clé> redirige vers /?salon=<id>) : entrer directement.
      if (salonDemande && !etat.salonId) { ouvrir(etat.couleur); rejoindre(salonDemande); }
    },
    etat,
  };
})();
