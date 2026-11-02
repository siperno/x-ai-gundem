"""One-time verified AI news post, Nov 2 2026. Fail closed, never retry uncertain writes."""
import json
import os
import random
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import publisher as p

STATE = "state/verified-ai-news-2026-11-02.json"
DAILY = "state/2026-11-02.json"
SOURCE = "https://www.reuters.com/business/energy/abu-dhabis-adnoc-g42-sign-deal-with-openai-sam-altman-travels-uae-2026-11-02/"
TEXT = (
    "OpenAI artık sadece sohbet ekranında değil. ⚡\n\n"
    "Abu Dabi’nin enerji devi ADNOC, G42 ve OpenAI ile anlaştı. "
    "Hedef, gelişmiş yapay zekâyı enerji operasyonlarına taşımak.\n\n"
    "AI artık sahada. Sizce sıradaki sektör hangisi?\n\n" + SOURCE
)

def graphic(path):
    w, h = 1200, 675
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (max(4, int(8 + 17*y/h + 5*x/w)),
                         max(10, int(19 + 19*y/h + 7*x/w)),
                         max(28, int(50 + 26*y/h + 10*x/w)))
    d = ImageDraw.Draw(im, "RGBA")
    # Stylized refinery silhouette and orange city lights
    random.seed(11)
    for x in range(600, 1210, 50):
        height = random.randint(100, 330)
        d.rectangle((x, h-height, x+random.randint(26, 62), h), fill=(8, 15, 30, 255))
        for yy in range(h-height+15, h-10, 35):
            d.line((x+4, yy, x+42, yy), fill=(255, 165, 62, 160), width=3)
    for x in (735, 910, 1070):
        d.rectangle((x, 180, x+30, 610), fill=(12, 22, 41, 255))
        d.rectangle((x-8, 180, x+38, 198), fill=(240, 151, 53, 255))
        d.line((x+15, 150, x+15, 180), fill=(230, 240, 255, 255), width=4)
    for k in range(11):
        y = 400 + k*19
        d.arc((420-k*5, y-250, 1270, y+170), 195, 337, fill=(20, 190, 250, 70+k*9), width=3)
    d.ellipse((730, 50, 1120, 430), outline=(16, 189, 250, 130), width=5)
    for j in range(13):
        y = 80+j*24
        d.line((790, y, 1090, y+60), fill=(37, 192, 250, 65), width=2)
    fontfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    smallfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    big = ImageFont.truetype(fontfile, 67)
    middle = ImageFont.truetype(fontfile, 48)
    small = ImageFont.truetype(smallfile, 31)
    d.rounded_rectangle((50, 46, 263, 92), radius=14, fill=(10, 125, 194, 220))
    d.text((72, 53), "AI HABER", font=ImageFont.truetype(fontfile, 23), fill=(255,255,255,255))
    d.text((50, 145), "YAPAY ZEKÂ", font=big, fill=(250, 250, 255, 255), stroke_width=1)
    d.text((50, 240), "ENERJİYE", font=big, fill=(255, 188, 64, 255))
    d.text((50, 333), "GİRİYOR", font=big, fill=(250, 250, 255, 255))
    d.rounded_rectangle((50, 475, 576, 551), radius=12, fill=(5, 16, 36, 230), outline=(27, 181, 244, 180), width=2)
    d.text((75, 492), "OpenAI  •  G42  •  ADNOC", font=small, fill=(237, 244, 255, 255))
    im.save(path, "JPEG", quality=90, optimize=True)

def main():
    previous, _ = p.get_file(STATE)
    if previous:
        print("Bu haber için yayın girişimi zaten mevcut; tekrar paylaşılmıyor.")
        return
    daily, _ = p.get_file(DAILY)
    if daily and daily.get("status") in ("attempting", "scheduled", "sent"):
        print("Bugünkü otomatik yayın kaydı var; ikinci gönderi oluşturulmadı.")
        return
    if p.weighted_length(TEXT) > 280:
        raise RuntimeError("X karakter sınırı aşıldı")
    org, cid = p.channel()
    Path("out").mkdir(exist_ok=True)
    path = Path("out/ai-energy-news.jpg")
    graphic(path)
    image_path = "media/verified-ai-news-2026-11-02.jpg"
    try:
        uploaded = p.put_file(image_path, path.read_bytes())
        url = f'https://raw.githubusercontent.com/{p.repo()}/{uploaded["commit"]["sha"]}/{image_path}'
        p.request(url, raw=True)
    except Exception as e:
        raise RuntimeError("Görsel barındırılamadı; görselsiz yayın yapılmadı") from e
    payload = {"text": TEXT, "channelId": cid, "schedulingType": "automatic",
               "mode": "shareNow", "assets": [{"image": {"url": url}}]}
    record = {"status": "attempting", "source": SOURCE, "text": TEXT,
              "requested_at": p.now().isoformat()}
    reservation = p.put_file(STATE, json.dumps(record, ensure_ascii=False).encode())
    result = p.gql('mutation($input: CreatePostInput!) { createPost(input: $input) { '
                   '... on PostActionSuccess { post { id status externalLink } } '
                   '... on MutationError { message } } }', {"input": payload})["createPost"]
    if "post" not in result:
        raise RuntimeError("Buffer gönderiyi reddetti; otomatik yeniden deneme yapılmadı")
    record.update(result["post"])
    sha = p.put_file(STATE, json.dumps(record, ensure_ascii=False).encode(),
                     reservation["content"]["sha"])["content"]["sha"]
    for _ in range(18):
        data = p.gql('query { posts(first: 100, input: {organizationId: ' + json.dumps(org) +
                     ', filter: {channelIds: [' + json.dumps(cid) + ']}}) { edges { node { id status externalLink } } } }')
        for edge in data["posts"]["edges"]:
            if edge["node"]["id"] == record["id"]:
                record.update(edge["node"])
        if record["status"] in ("sent", "error"):
            break
        time.sleep(10)
    p.put_file(STATE, json.dumps(record, ensure_ascii=False).encode(), sha)
    print(json.dumps(record, ensure_ascii=False))
    if record["status"] != "sent":
        raise RuntimeError("X teslimi doğrulanmadı; kör tekrar yayın yapılmayacak")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Yayın denemesi güvenli şekilde durdu: " + type(exc).__name__)
        raise SystemExit(1)
