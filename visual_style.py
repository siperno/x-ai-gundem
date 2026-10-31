"""Approved cinematic typography. Raster glyph artwork; no font file required."""
import json, math
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
ASSETS=Path(__file__).parent/'assets'
def upper(s):
    return s.translate(str.maketrans({'i':'İ','ı':'I'})).upper()
class Display:
    def __init__(self, image):
        self.image=image
        self.atlas=Image.open(ASSETS/'display-glyphs.png').convert('L')
        self.metrics=json.loads((ASSETS/'display-glyphs.json').read_text())
    def text(self, value, x,y,size,color='white',max_width=1700):
        value=upper(str(value)); chars=[self.metrics.get(c,self.metrics['?']) for c in value]
        advance=sum(c['advance'] for c in chars)
        scale=min(size/160,max_width/max(1,advance))
        top=min((c['offset'][1] for c in chars),default=0)
        cursor=x-advance*scale/2
        for c in chars:
            box=c['box']; w=box[2]-box[0];h=box[3]-box[1]
            if w and h:
                mask=self.atlas.crop(box).resize((max(1,round(w*scale)),max(1,round(h*scale))),Image.Resampling.LANCZOS)
                self.image.paste(color,(round(cursor+c['offset'][0]*scale),round(y+(c['offset'][1]-top)*scale)),mask)
            cursor+=c['advance']*scale

def make_card(repos,end,path):
    im=Image.open(ASSETS/'background.jpg').convert('RGB')
    shade=Image.new('RGBA',im.size);sd=ImageDraw.Draw(shade)
    for y in range(1080):
        a=int(180*max(0,1-y/360)) if y<360 else int(220*max(0,(y-790)/290))
        sd.line((0,y,1920,y),fill=(2,3,9,a))
    im=Image.alpha_composite(im.convert('RGBA'),shade).convert('RGB');d=ImageDraw.Draw(im);t=Display(im)
    t.text('AÇIK KAYNAK AI',960,65,122,'#F12F43')
    t.text('GELİŞTİRİCİLER İÇİN GITHUB KEŞİFLERİ',960,217,34,'#D2D8E3')
    for i,r in enumerate(repos[:2]):
        x=[570,1360][i];col=['#FF4C58','#72C5FF'][i]
        name=r['name'].split('/')[-1].replace('-',' ').upper()
        t.text(name,x,296,58,max_width=700)
        d.rounded_rectangle((x-240,358,x+240,480),radius=14,fill='#080C16',outline=col,width=2)
        d.rounded_rectangle((x-240,358,x-231,480),radius=4,fill=col)
        pts=[(x-190+math.cos(-math.pi/2+j*math.pi/5)*(22 if j%2==0 else 10),408+math.sin(-math.pi/2+j*math.pi/5)*(22 if j%2==0 else 10)) for j in range(10)]
        d.polygon(pts,fill='#FFD36A')
        t.text(f"{r['stars']:,}".replace(',','.'),x+12,374,78,max_width=350)
        t.text('GITHUB YILDIZI',x+16,451,18,'#B7C3D8')
        label={'explosion/spaCy':'DOĞAL DİL İŞLEME','Lightning-AI/pytorch-lightning':'MODEL EĞİTİMİ'}.get(r['name'],r.get('language') or 'AÇIK KAYNAK')
        d.rounded_rectangle((x-300,890,x+300,966),radius=12,fill='#080C16',outline=col,width=2)
        d.rounded_rectangle((x-300,890,x-292,966),radius=4,fill=col)
        t.text(label,x,904,48,max_width=555)
    d.line((100,982,1820,982),fill='#414651',width=1)
    t.text('@KUYTANCAGLAR',250,1011,26,'#D7DBE3')
    date=end.astimezone(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y')
    t.text('TOPLAM GITHUB YILDIZLARI · '+date,1500,1011,25,'#ABB3C2',max_width=650)
    im.save(path)
