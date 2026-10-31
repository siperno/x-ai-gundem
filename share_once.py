"""User-authorized single immediate post; durable guard prevents duplicate sends."""
import json
import os
import time
from pathlib import Path
import publisher as p

STATE = 'state/manual-example-2026-10-31.json'


def main():
    previous, _ = p.get_file(STATE)
    if previous:
        print('Bu tek seferlik paylaşım daha önce başlatıldı; tekrar gönderilmiyor.')
        print(json.dumps(previous, ensure_ascii=False))
        return
    org, cid = p.channel()
    moment = p.now()
    repos = p.repositories(moment)
    text = 'Açık kaynak AI araçları keşfi!\n\n' + '\n\n'.join(
        f"{r['name']} · {r['stars']:,} yıldız\n{r['url']}" for r in repos
    ) + '\n\nYıldızlar güncel toplam sayıdır. #YapayZeka'
    if p.weighted_length(text) > 280:
        raise RuntimeError('Karakter sınırı aşıldı')
    Path('out').mkdir(exist_ok=True)
    p.make_card(repos, moment, 'out/manual.png')
    image_path = 'media/manual-' + os.environ['GITHUB_RUN_ID'] + '.png'
    uploaded = p.put_file(image_path, Path('out/manual.png').read_bytes())
    url = f'https://raw.githubusercontent.com/{p.repo()}/{uploaded["commit"]["sha"]}/{image_path}'
    p.request(url, raw=True)
    payload = {'text': text, 'channelId': cid, 'schedulingType': 'automatic',
               'mode': 'shareNow', 'assets': [{'image': {'url': url}}]}
    record = {'status': 'attempting', 'text': text, 'requested_at': moment.isoformat()}
    saved = p.put_file(STATE, json.dumps(record, ensure_ascii=False).encode())
    sha = saved['content']['sha']
    result = p.gql('mutation($input: CreatePostInput!) { createPost(input: $input) { '
                   '... on PostActionSuccess { post { id status externalLink } } '
                   '... on MutationError { message } } }', {'input': payload})['createPost']
    if 'post' not in result:
        raise RuntimeError('Buffer gönderiyi reddetti; tekrar gönderilmedi')
    record.update(result['post'])
    updated = p.put_file(STATE, json.dumps(record, ensure_ascii=False).encode(), sha)
    sha = updated['content']['sha']
    for _ in range(18):
        data = p.gql('query { posts(first: 100, input: {organizationId: ' + json.dumps(org) +
                     ', filter: {channelIds: [' + json.dumps(cid) + ']}}) { edges { node { id status externalLink } } } }')
        for edge in data['posts']['edges']:
            post = edge['node']
            if post['id'] == record['id']:
                record.update(post)
        if record['status'] in ('sent', 'error'):
            break
        time.sleep(10)
    p.put_file(STATE, json.dumps(record, ensure_ascii=False).encode(), sha)
    print(json.dumps(record, ensure_ascii=False))
    if record['status'] != 'sent':
        raise RuntimeError('Buffer henüz sent teyidi vermedi; kayıt kontrol edilmeli, tekrar göndermeyin')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Paylaşım kontrolü durdu: ' + type(exc).__name__)
        raise SystemExit(1)
