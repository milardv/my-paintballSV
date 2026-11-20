# Génère les sons du mode paintball avec l'API Sound Effects d'ElevenLabs.
# Clé lue dans ELEVENLABS_API_KEY. Sorties : assets/paintball/sons-elevenlabs/<nom>.mp3 + prompts.json
import json,os,sys,urllib.request
racine=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dossier=os.path.join(racine,"assets/paintball/sons-elevenlabs")
SONS={
 "ambiance_parc":(22,True,"Peaceful Provencal chateau park in Marseille on a warm afternoon, cicadas chirping, gentle wind in pine trees, distant birds, a small fountain trickling, seamless ambient loop, no music, no voices"),
 "ambiance_interieur":(20,True,"Interior ambience of a grand old French chateau hall, clearly audible room tone, wind howling softly against tall old windows, wooden floor creaks, an antique pendulum clock ticking steadily nearby, distant muffled cicadas outside, seamless ambient loop, no music, no voices"),
 "tir_marqueur":(0.6,False,"Single paintball marker shot, sharp pneumatic compressed air pop with a short hollow thump, close up, dry, no echo"),
 "impact_peinture":(0.5,False,"Paintball hitting a hard wall and bursting, wet splat with a short crack, close up"),
 "cible_touchee":(0.8,False,"Paintball smacking a wooden target board, solid wet thwack followed by a short satisfying metallic ding"),
 "recharge":(1.5,False,"Reloading a paintball marker: plastic hopper lid snapping open, paintballs rattling and pouring into the hopper, lid clicking shut"),
 "chargeur_vide":(0.4,False,"Dry trigger click of an empty air gun, light mechanical click, close up"),
 "explosion_peinture":(2.2,False,"Huge cartoon paint grenade explosion: a deep punchy boom with a sub-bass thump, a big wet splash of thick paint bursting in all directions, splatters raining down on the ground, stylish arcade video game impact, close up, no music, no voices"),
 "ambiance_neige":(22,True,"Quiet snowy winter park ambience, soft gusts of cold wind through bare trees, gentle hiss of falling snow, muffled distant silence, very calm, seamless ambient loop, no birds, no insects, no music, no voices"),
 "pas_neige":(0.5,False,"Single footstep in fresh powder snow, soft compressing crunch, close up, dry, no echo"),
 "menu_validation":(0.6,False,"Short elegant user interface confirm sound, soft wooden click with a bright airy chime, game menu"),
}
cle=os.environ["ELEVENLABS_API_KEY"];prompts={}
for nom,(duree,boucle,texte) in SONS.items():
    if len(sys.argv)>1 and nom not in sys.argv[1:]: continue
    corps={"text":texte,"duration_seconds":max(0.5,duree),"prompt_influence":0.55,"model_id":"eleven_text_to_sound_v2"}
    if boucle: corps["loop"]=True
    req=urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128",data=json.dumps(corps).encode(),headers={"xi-api-key":cle,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=120) as r: data=r.read()
    except urllib.error.HTTPError as e: print(nom,"ERREUR",e.code,e.read()[:300]);continue
    open(os.path.join(dossier,nom+".mp3"),"wb").write(data);prompts[nom]=corps;print(nom,len(data),"octets")
f=os.path.join(dossier,"prompts.json");ancien=json.load(open(f)) if os.path.exists(f) else {}
ancien.update(prompts);json.dump(ancien,open(f,"w"),indent=1,ensure_ascii=False)
