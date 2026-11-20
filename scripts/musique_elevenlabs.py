# Génère la musique de fond du mode paintball : ambiance provençale tranquille, village des années 1930
# (accordéon musette, mandoline, guitare, clarinette). API Music d'ElevenLabs si le compte y a accès
# (morceau de 2 min), sinon API Sound Effects (boucle de 30 s). Clé lue dans ELEVENLABS_API_KEY.
# Sortie : assets/paintball/sons-elevenlabs/musique_ambiance.mp3 + prompts.json, puis copie en OGG dans
# unity/Assets/Chateau/Resources/Sons (ffmpeg).
import json,os,subprocess,urllib.error,urllib.request
racine=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dossier=os.path.join(racine,"assets/paintball/sons-elevenlabs")
texte=("Chill instrumental background music evoking a lazy summer afternoon in a small Provencal village in the 1930s: "
       "gentle accordion musette melody, plucked mandolin and warm nylon guitar, soft clarinet answering, light upright bass, "
       "slow relaxed tempo, nostalgic, sunny and peaceful, pastis on the terrace under the plane trees, no drums, no vocals")
cle=os.environ["ELEVENLABS_API_KEY"]

def appel(url,corps):
    req=urllib.request.Request(url,data=json.dumps(corps).encode(),headers={"xi-api-key":cle,"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=600) as r: return r.read()

try:
    corps={"prompt":texte,"music_length_ms":120000,"model_id":"music_v1","force_instrumental":True}
    data=appel("https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128",corps);api="music"
except urllib.error.HTTPError as e:
    print("API Music indisponible :",e.code,e.read()[:200])
    corps={"text":texte+", seamless loop","duration_seconds":30,"prompt_influence":0.6,"model_id":"eleven_text_to_sound_v2","loop":True}
    data=appel("https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128",corps);api="sound-generation"
mp3=os.path.join(dossier,"musique_ambiance.mp3")
open(mp3,"wb").write(data);print(api,len(data),"octets")
f=os.path.join(dossier,"prompts.json");ancien=json.load(open(f)) if os.path.exists(f) else {}
ancien["musique_ambiance"]=dict(corps,api=api);json.dump(ancien,open(f,"w"),indent=1,ensure_ascii=False)
ogg=os.path.join(racine,"unity/Assets/Chateau/Resources/Sons/musique_ambiance.ogg")
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",mp3,"-c:a","libvorbis","-q:a","4",ogg],check=True)
