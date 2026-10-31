"""Free, fail-closed daily publishing. No paid AI APIs, no secret logging."""
import base64
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
BERLIN = ZoneInfo('Europe/Berlin')
TARGET = 'kuytancaglar'
FEEDS = [
    ('OpenAI', 'https://openai.com/news/rss.xml', 'openai.com', 'en'),
    ('Google AI', 'https://blog.google/technology/ai/rss/', 'blog.google', 'en'),
    ('TRT Haber', 'https://www.trthaber.com/bilim_teknoloji_articles.rss', 'www.trthaber.com', 'tr'),
]
AI_WORDS = re.compile(r'yapay zek[aâ]|\bAI\b|\bLLM\b|ChatGPT|Claude|Gemini|GPT|machine learning', re.I)


def now():
    return dt.datetime.now(UTC)


def target_time(moment):
    return moment.astimezone(BERLIN).replace(hour=8, minute=30, second=0, microsecond=0)


def request(url, payload=None, token=None, method=None, raw=False):
    headers = {'User-Agent': 'x-ai-gundem/1.0 (+https://github.com/siperno/x-ai-gundem)'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # No automatic write retry: an uncertain response must never double-publish.
    with urllib.request.urlopen(req, timeout=40) as response:
        body = response.read(8_000_000)
        return body if raw else json.loads(body)


def gql(query, variables=None):
    key = os.environ.get('BUFFER_API_KEY')
    if not key:
        raise RuntimeError('BUFFER_API_KEY secret eksik')
    result = request('https://api.buffer.com', {'query': query, 'variables': variables or {}}, key)
    if result.get('errors'):
        # GraphQL server messages could contain submitted values. Never log raw responses.
        raise RuntimeError('Buffer GraphQL isteği reddedildi; anahtar yetkilerini ve API şemasını kontrol edin')
    return result['data']


def gh(path, payload=None, method=None):
    return request('https://api.github.com/' + path, payload,
                   os.environ.get('GITHUB_TOKEN'), method)


def repo():
    return os.environ.get('GITHUB_REPOSITORY', 'siperno/x-ai-gundem')


def get_file(path):
    try:
        item = gh(f'repos/{repo()}/contents/{path}')
        return json.loads(base64.b64decode(item['content'])), item['sha']
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None
        raise


def put_file(path, data, sha=None):
    body = {'message': f'Update {path}', 'content': base64.b64encode(data).decode(), 'branch': 'main'}
    if sha:
        body['sha'] = sha
    return gh(f'repos/{repo()}/contents/{path}', body, 'PUT')


def channel():
    orgs = gql('{ account { organizations { id } } }')['account']['organizations']
    matches = []
    # Introspection avoids guessing username field names across API revisions.
    schema = gql('{ __type(name: "Channel") { fields { name } } }')
    fields = {f['name'] for f in (schema.get('__type') or {}).get('fields', [])}
    identity = [f for f in ('username', 'url', 'profileUrl') if f in fields]
    for org in orgs:
        query = 'query { channels(input: {organizationId: ' + json.dumps(org['id']) + '}) { id name service ' + ' '.join(identity) + ' } }'
        for c in gql(query)['channels']:
            identifiers = [str(c.get(f) or '').lower().strip().lstrip('@') for f in ['name'] + identity]
            is_target = any(v == TARGET or v.rstrip('/').split('/')[-1].lstrip('@') == TARGET for v in identifiers)
            if c['service'] == 'twitter' and is_target:
                matches.append((org['id'], c['id']))
    if len(matches) != 1:
        raise RuntimeError('@kuytancaglar X kanalı tekil olarak doğrulanamadı; yanlış hesaba yayın engellendi')
    return matches[0]


def gate():
    mode = os.environ.get('RUN_MODE', 'preview')
    moment = now()
    due = target_time(moment)
    if mode == 'publish' and not (due - dt.timedelta(minutes=60) <= moment <= due + dt.timedelta(minutes=60)):
        print('Yayın penceresi dışında: yalnızca 07.30–09.30 Berlin arasında yayınlanır.')
        return
    state, _ = get_file(f'state/{due.date()}.json')
    if mode == 'publish' and state:
        if state['status'] == 'scheduled':
            print('Bugünkü yayın zaten Buffer’a iletildi; tekrar oluşturulmadı.')
            return
        raise RuntimeError('Önceki yayın denemesinin sonucu belirsiz; Buffer kontrol edilmeden tekrar gönderilmeyecek')
    channel()
    print('Buffer erişimi ve @kuytancaglar X kanalı doğrulandı.')
    if mode == 'check':
        # Also validate posts-read permission, needed for operational inspection.
        org, cid = channel()
        gql('query { posts(first: 1, input: {organizationId: ' + json.dumps(org) +
            ', filter: {channelIds: [' + json.dumps(cid) + ']}}) { edges { node { id } } } }')
        print('Gönderi okuma yetkisi doğrulandı. Yazma yetkisi ilk gerçek zamanlamada doğrulanır.')
        return
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write('proceed=true\n')


def parsed_date(value):
    try:
        date = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError):
        date = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Timezone missing')
    return date.astimezone(UTC)


def within_window(published, end):
    return end - dt.timedelta(hours=24) <= published <= end


def clean(value):
    return ' '.join(html.unescape(re.sub('<[^>]+>', '', value)).split())


def safe_link(url, host):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != host or parts.username or parts.password:
        return False
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 x-ai-gundem'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return urllib.parse.urlsplit(response.url).hostname == host and response.status == 200


def news(end):
    items, healthy = [], 0
    for name, url, host, lang in FEEDS:
        try:
            root = ET.fromstring(request(url, raw=True))
            healthy += 1
            for entry in root.findall('.//item'):
                title = clean(entry.findtext('title', ''))
                link = entry.findtext('link', '').strip()
                try:
                    published = parsed_date(entry.findtext('pubDate', ''))
                except (ValueError, TypeError):
                    continue
                if not within_window(published, end) or (lang == 'tr' and not AI_WORDS.search(title)):
                    continue
                if not title or len(title.split()) > 25:
                    continue
                try:
                    if not safe_link(link, host):
                        continue
                except Exception:
                    continue
                items.append(dict(title=title, url=link, source=name, language=lang,
                                  published=published.isoformat()))
        except Exception:
            print(f'Kaynak erişilemiyor: {name}; eski haber kullanılmayacak.')
    if not healthy:
        raise RuntimeError('Tüm haber kaynakları erişilemez; yayın durduruldu')
    unique = {i['url']: i for i in items}
    return sorted(unique.values(), key=lambda i: i['published'], reverse=True)[:3]


def repositories(end):
    query = 'topic:artificial-intelligence stars:>=1000 archived:false fork:false'
    data = gh('search/repositories?' + urllib.parse.urlencode({'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 30}))
    candidates = []
    for r in data.get('items', []):
        # Recent activity is not claimed to be a new release or star growth.
        if parsed_date(r['pushed_at']) > end or parsed_date(r['pushed_at']) < end - dt.timedelta(days=30):
            continue
        candidates.append(r)
    if not candidates:
        raise RuntimeError('Doğrulanmış aktif yüksek yıldızlı AI reposu bulunamadı')
    # Rotate deterministically, so the same top repository is not posted daily.
    start = end.astimezone(BERLIN).date().toordinal() % len(candidates)
    selected = (candidates[start:] + candidates[:start])[:2]
    return [{'name': r['full_name'], 'stars': r['stargazers_count'], 'url': r['html_url'],
             'language': r.get('language') or 'Belirtilmemiş', 'observed_at': end.isoformat()} for r in selected]


def translator():
    import argostranslate.package as package
    import argostranslate.translate as translate
    installed = package.get_installed_packages()
    if not any(p.from_code == 'en' and p.to_code == 'tr' for p in installed):
        package.update_package_index()
        model = next(p for p in package.get_available_packages() if p.from_code == 'en' and p.to_code == 'tr')
        package.install_from_path(model.download())
    return lambda text: clean(translate.translate(text, 'en', 'tr'))


def clip(value, length):
    return value if len(value) <= length else value[:length-1].rsplit(' ', 1)[0] + '…'


def build_posts(items, repos, end, translate):
    stamp = end.astimezone(BERLIN).strftime('%d.%m.%Y %H:%M')
    posts = [f'AI gündemi | {stamp} Berlin\nSon 24 saatte kaynaklarda yayımlanan haberler ve yüksek yıldızlı GitHub keşifleri.\nKaynak bağlantıları aşağıda. #YapayZeka']
    for item in items:
        item['title_tr'] = translate(item['title']) if item['language'] == 'en' else item['title']
        prefix = item['source'] + ' duyurusu' if item['language'] == 'en' else item['source'] + ' haberi'
        posts.append(f"{prefix}:\n{clip(item['title_tr'], 170)}\n{item['url']}")
    if not items:
        posts.append('Kontrol edilen kaynaklarda son 24 saat için tarih ve bağlantı kontrollerini geçen yeni AI haberi bulunamadı. Eski haberleri yeniymiş gibi paylaşmıyorum.')
    for r in repos:
        posts.append(f"GitHub keşfi: {r['name']}\n{r['stars']:,} yıldız · {r['language']}\nAI etiketli, son 30 günde kod güncellemesi olan repo. Yıldızlar toplam sayıdır.\n{r['url']}")
    # Conservative bound: every non-ASCII code point counts double, URL counts 23.
    for text in posts:
        if weighted_length(text) > 280:
            raise RuntimeError('X karakter sınırı aşıldı; yayın engellendi')
    return posts


def weighted_length(text):
    replaced = re.sub(r'https://\S+', 'x' * 23, text)
    return sum(1 if ord(c) <= 0x10ff else 2 for c in replaced)


def make_card(repos, end, path):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (1200, 675), '#080e20')
    d = ImageDraw.Draw(img)
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not Path(font_path).exists():
        font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
    def font(size):
        return ImageFont.truetype(font_path, size)
    for x in range(0, 1200, 60):
        d.line((x, 0, x, 675), fill='#132039')
    for y in range(0, 675, 60):
        d.line((0, y, 1200, y), fill='#132039')
    d.rounded_rectangle((55, 46, 1145, 630), radius=30, fill='#111c32', outline='#31567a', width=2)
    d.text((90, 74), 'AI GÜNDEMİ', font=font(62), fill='#f1f7ff')
    d.text((92, 155), end.astimezone(BERLIN).strftime('%d.%m.%Y') + '  /  GITHUB KEŞİFLERİ', font=font(25), fill='#69e4cf')
    for idx, r in enumerate(repos):
        y = 235 + idx * 150
        d.text((92, y), clip(r['name'], 45), font=font(31), fill='#f1f7ff')
        d.text((92, y + 51), f"{r['stars']:,} YILDIZ   ·   {r['language']}", font=font(26), fill='#69e4cf')
    d.text((92, 576), '@kuytancaglar   |   Kaynaklar paylaşım zincirinde', font=font(24), fill='#96a9c5')
    img.save(path)


def run():
    mode = os.environ.get('RUN_MODE', 'preview')
    end = now()
    due = target_time(end)
    if mode == 'publish' and not (due - dt.timedelta(hours=1) <= end <= due + dt.timedelta(hours=1)):
        raise RuntimeError('Yayın penceresi dışında')
    state_path = f'state/{due.date()}.json'
    old, _ = get_file(state_path)
    if mode == 'publish' and old:
        raise RuntimeError('Günlük kayıt mevcut; tekrarlı yayın engellendi')
    org, cid = channel()
    items = news(end)
    repos = repositories(end)
    tr = translator() if any(i['language'] == 'en' for i in items) else lambda x: x
    posts = build_posts(items, repos, end, tr)
    Path('out').mkdir(exist_ok=True)
    evidence = {'collected_at': end.isoformat(), 'window_start': (end-dt.timedelta(hours=24)).isoformat(),
                'news': items, 'repositories': repos, 'posts': posts}
    Path('out/preview.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    make_card(repos, end, 'out/card.png')
    print(f'{len(items)} güncel haber ve {len(repos)} repo hazırlandı. İçerik out/preview.json dosyasında.')
    if mode != 'publish':
        print('Önizleme: Buffer’a hiçbir gönderi oluşturulmadı.')
        return
    # Publish only today's current facts; severe delays never queue yesterday's digest.
    current = now()
    if current > due + dt.timedelta(hours=1):
        raise RuntimeError('Hazırlık fazla gecikti; bugünkü yayın iptal edildi')
    publish_at = max(due.astimezone(UTC), current + dt.timedelta(minutes=3))
    image_url = None
    try:
        image_path = f'media/{due.date()}.png'
        result = put_file(image_path, Path('out/card.png').read_bytes())
        image_url = f'https://raw.githubusercontent.com/{repo()}/{result["commit"]["sha"]}/{image_path}'
        request(image_url, raw=True)
    except Exception:
        image_url = None
        print('Görsel barındırma kullanılamadı; ücretsiz metin/bağlantı yedeği kullanılacak.')
    thread = [{'text': p} for p in posts]
    if image_url:
        thread[0]['assets'] = [{'image': {'url': image_url}}]
    payload = {'text': posts[0], 'channelId': cid, 'schedulingType': 'automatic',
               'mode': 'customScheduled', 'dueAt': publish_at.isoformat(),
               'metadata': {'twitter': {'thread': thread}}}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    record = {'date': str(due.date()), 'status': 'attempting', 'due_at': publish_at.isoformat(),
              'digest': digest, 'run_id': os.environ.get('GITHUB_RUN_ID')}
    # Durable reservation BEFORE external side effect. If result is uncertain, stop.
    reservation = put_file(state_path, json.dumps(record).encode())
    result = gql('mutation($input: CreatePostInput!) { createPost(input: $input) { '
                 '... on PostActionSuccess { post { id dueAt status } } '
                 '... on MutationError { message } } }', {'input': payload})['createPost']
    if 'post' not in result:
        raise RuntimeError('Buffer zamanlamayı reddetti; günlük kayıt inceleme için kilitli bırakıldı')
    record.update(status='scheduled', post_id=result['post']['id'])
    put_file(state_path, json.dumps(record).encode(), reservation['content']['sha'])
    print('Buffer gönderiyi kabul etti. Yayın zamanı: ' + publish_at.astimezone(BERLIN).isoformat())
    print('Bu sonuç X teslim teyidi değildir; Buffer yayın hataları ayrıca kontrol edilmelidir.')


if __name__ == '__main__':
    try:
        {'gate': gate, 'run': run}[sys.argv[1]]()
    except Exception as exc:
        # Do not print traceback, request headers, tokens, or remote response bodies.
        if isinstance(exc, RuntimeError):
            print('HATA: ' + str(exc), file=sys.stderr)
        elif isinstance(exc, urllib.error.HTTPError):
            print(f'HATA: HTTP {exc.code}; servis erişimi veya yetkileri kontrol edilmeli.', file=sys.stderr)
        else:
            print('HATA: ' + type(exc).__name__ + '; yayın güvenli biçimde durduruldu.', file=sys.stderr)
        sys.exit(1)
