import datetime as dt
import unittest
from unittest.mock import patch
import publisher as p

class PublishingTests(unittest.TestCase):
    def test_dst(self):
        for day, utc_hour in [('2026-03-28', 7), ('2026-03-29', 6), ('2026-10-24', 6), ('2026-10-25', 7)]:
            moment = dt.datetime.fromisoformat(day + 'T05:00:00+00:00')
            self.assertEqual(p.target_time(moment).astimezone(p.UTC).hour, utc_hour)

    def test_window_rejects_old_and_future(self):
        end = dt.datetime(2026, 10, 31, 7, tzinfo=p.UTC)
        self.assertTrue(p.within_window(end - dt.timedelta(hours=23), end))
        self.assertFalse(p.within_window(end - dt.timedelta(hours=25), end))
        self.assertFalse(p.within_window(end + dt.timedelta(seconds=1), end))

    def test_timestamp_without_timezone_rejected(self):
        with self.assertRaises(ValueError):
            p.parsed_date('2026-10-31T07:00:00')

    def test_posts_fit_and_do_not_claim_recent_stars(self):
        repos = [{'name': 'org/project', 'stars': 15000, 'language': 'Python', 'url': 'https://github.com/org/project'}]
        items = [{'title': 'Model released', 'source': 'OpenAI', 'language': 'en', 'url': 'https://openai.com/example'}]
        posts = p.build_posts(items, repos, p.now(), lambda _: 'Yeni model duyuruldu')
        self.assertTrue(all(p.weighted_length(x) <= 280 for x in posts))
        self.assertIn('toplam sayıdır', posts[-1])

    def test_no_news_is_explicit(self):
        posts = p.build_posts([], [], p.now(), lambda _: '')
        self.assertIn('bulunamadı', posts[1])

    def test_existing_reservation_blocks_mutation(self):
        moment = dt.datetime(2026, 10, 31, 7, 0, tzinfo=p.UTC)
        with patch.dict(p.os.environ, {'RUN_MODE': 'publish'}), patch.object(p, 'now', return_value=moment), patch.object(p, 'get_file', return_value=({'status': 'attempting'}, 'sha')), patch.object(p, 'gql') as gql:
            with self.assertRaises(RuntimeError):
                p.run()
            gql.assert_not_called()

    def test_ambiguous_target_blocked(self):
        responses = [
            {'account': {'organizations': [{'id': 'org'}]}},
            {'__type': {'fields': [{'name': 'username'}]}},
            {'channels': [{'id': 'wrong', 'name': 'Other', 'username': 'other', 'service': 'twitter'}]},
        ]
        with patch.object(p, 'gql', side_effect=responses):
            with self.assertRaises(RuntimeError):
                p.channel()

if __name__ == '__main__':
    unittest.main()
