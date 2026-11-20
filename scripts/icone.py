# Icône du jeu : tache de peinture framboise sur fond vert nuit, silhouette du château, réticule.
import math,random,os
from PIL import Image,ImageDraw,ImageFilter
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));OUT=os.path.join(R,"assets/icone")
N=2048;img=Image.new("RGBA",(N,N),(0,0,0,0));d=ImageDraw.Draw(img)
# fond : carré arrondi, dégradé vertical
fond=Image.new("RGBA",(N,N));fd=ImageDraw.Draw(fond)
for y in range(N):
    t=y/N;c=(int(11+18*t),int(36-6*t),int(29-4*t),255);fd.line([(0,y),(N,y)],fill=c)
masque=Image.new("L",(N,N),0);ImageDraw.Draw(masque).rounded_rectangle([0,0,N-1,N-1],radius=int(N*.22),fill=255)
img.paste(fond,(0,0),masque)
# halo
halo=Image.new("RGBA",(N,N),(0,0,0,0));ImageDraw.Draw(halo).ellipse([N*.18,N*.12,N*.82,N*.76],fill=(64,206,228,70))
img=Image.alpha_composite(img,halo.filter(ImageFilter.GaussianBlur(N*.08)))
# tache
rnd=random.Random(7);tache=Image.new("L",(N,N),0);td=ImageDraw.Draw(tache)
cx,cy,r0=N*.5,N*.43,N*.2
pts=[]
for i in range(72):
    a=i/72*2*math.pi;r=r0*(1+.12*math.sin(5*a+1)+.07*math.sin(11*a)+rnd.uniform(-.04,.04))
    pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
td.polygon(pts,fill=255)
for i in range(13):
    a=rnd.uniform(0,2*math.pi);L=r0*rnd.uniform(1.0,1.6);w=N*rnd.uniform(.008,.018)
    for k in range(40):
        t=k/39;rr=w*(2.2-1.5*t)+w*.9*t*t*3*(t>.9);x=cx+L*t*math.cos(a);y=cy+L*t*math.sin(a)
        td.ellipse([x-rr,y-rr,x+rr,y+rr],fill=255)
    x1,y1=cx+L*math.cos(a),cy+L*math.sin(a);td.ellipse([x1-w*1.4,y1-w*1.4,x1+w*1.4,y1+w*1.4],fill=255)
for i in range(22):
    a=rnd.uniform(0,2*math.pi);L=r0*rnd.uniform(1.8,2.25);w=N*rnd.uniform(.006,.02)
    x1,y1=cx+L*math.cos(a),cy+L*math.sin(a)
    if N*.08<x1<N*.92 and N*.08<y1<N*.9: td.ellipse([x1-w,y1-w,x1+w,y1+w],fill=255)
tache=tache.filter(ImageFilter.GaussianBlur(N*.004)).point(lambda v:255 if v>128 else 0)
couleur=Image.new("RGBA",(N,N),(255,59,135,255))
# reflet brillant
br=Image.new("L",(N,N),0);ImageDraw.Draw(br).ellipse([cx-r0*.55,cy-r0*.75,cx+r0*.05,cy-r0*.25],fill=120)
couleur=Image.composite(Image.new("RGBA",(N,N),(255,170,205,255)),couleur,br.filter(ImageFilter.GaussianBlur(N*.03)))
ombre=Image.new("RGBA",(N,N),(0,0,0,0));ombre.paste((0,0,0,110),(int(N*.012),int(N*.02)),tache)
img=Image.alpha_composite(img,ombre.filter(ImageFilter.GaussianBlur(N*.012)))
t2=Image.new("RGBA",(N,N),(0,0,0,0));t2.paste(couleur,(0,0),tache);img=Image.alpha_composite(img,t2)
# silhouette du château (ivoire)
s=ImageDraw.Draw(img);iv=(244,240,231,255);base=N*.88;u=N/100*.72;ox=N*.14
s.rectangle([ox+20*u,base-14*u,ox+80*u,base],fill=iv)              # corps
s.rectangle([ox+14*u,base-10*u,ox+24*u,base],fill=iv);s.rectangle([ox+76*u,base-10*u,ox+86*u,base],fill=iv) # pavillons
s.rectangle([ox+38*u,base-21*u,ox+62*u,base-14*u],fill=iv)          # attique
s.polygon([(ox+36*u,base-21*u),(ox+50*u,base-29*u),(ox+64*u,base-21*u)],fill=iv) # toit central
for x in (30,42,58,70): s.rectangle([ox+x*u,base-19*u,ox+(x+2.4)*u,base-14*u],fill=iv) # souches
fn=(14,34,28,255)
for i in range(7):
    x=ox+26*u+i*7.4*u;s.rectangle([x,base-11*u,x+3*u,base-5*u],fill=fn)
s.rectangle([N*.08,base,N*.92,base+N*.008],fill=(173,148,100,255))
img.putalpha(Image.composite(img.getchannel("A"),Image.new("L",(N,N),0),masque))
# réticule blanc au centre de la tache
rc=Image.new("RGBA",(N,N),(0,0,0,0));rd=ImageDraw.Draw(rc);g=N*.035;l=N*.075;w=int(N*.018)
for dx,dy in ((0,-1),(1,0),(0,1),(-1,0)):
    rd.line([(cx+dx*g,cy+dy*g),(cx+dx*(g+l),cy+dy*(g+l))],fill=(255,255,255,255),width=w)
rd.ellipse([cx-w*.8,cy-w*.8,cx+w*.8,cy+w*.8],fill=(255,255,255,255))
rd.ellipse([cx-g-l*1.15,cy-g-l*1.15,cx+g+l*1.15,cy+g+l*1.15],outline=(255,255,255,235),width=int(w*.7))
sh=Image.new("RGBA",(N,N),(0,0,0,0));sh.paste((0,0,0,120),(0,0),rc.getchannel("A"))
img=Image.alpha_composite(img,sh.filter(ImageFilter.GaussianBlur(N*.006)));img=Image.alpha_composite(img,rc)
for t in (1024,512,192,180,64,32,16):
    img.resize((t,t),Image.LANCZOS).save(os.path.join(OUT,f"icone-{t}.png"))
print("ok")
