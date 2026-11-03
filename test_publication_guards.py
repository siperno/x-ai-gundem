import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import publisher as p
import share_news_2026_11_02 as news


class PublicationGuards(unittest.TestCase):
    def test_late_missing_day_fails_without_buffer_access(self):
        moment = dt.datetime(2026, 11, 2, 16, tzinfo=p.UTC)
        with patch.dict(p.os.environ, RUN_MODE='publish'), patch.object(p, 'now', return_value=moment), patch.object(p, 'get_file', return_value=(None, None)), patch.object(p, 'channel') as channel:
            with self.assertRaises(RuntimeError):
                p.gate()
            channel.assert_not_called()

    def test_late_completed_day_is_safe_noop(self):
        moment = dt.datetime(2026, 11, 2, 16, tzinfo=p.UTC)
        for status in ('scheduled', 'sent'):
            with self.subTest(status=status), patch.dict(p.os.environ, RUN_MODE='publish'), patch.object(p, 'now', return_value=moment), patch.object(p, 'get_file', return_value=({'status': status}, 'sha')), patch.object(p, 'channel') as channel:
                p.gate()
                channel.assert_not_called()

    def test_any_daily_record_blocks_one_time_post(self):
        for status in ('attempting', 'scheduled', 'sent', 'error'):
            with self.subTest(status=status), patch.object(p, 'get_file', side_effect=[(None, None), ({'status': status}, 'sha')]), patch.object(p, 'gql') as gql:
                news.main()
                gql.assert_not_called()

    def exercise_one_time(self, outcome):
        records = {}
        writes = []
        def put(path, data, sha=None):
            if path.startswith('state/'):
                if path in records and sha is None:
                    raise RuntimeError('reservation conflict')
                records[path] = p.json.loads(data)
                writes.append((path, sha))
            return {'content': {'sha': str(len(writes))}, 'commit': {'sha': 'commit'}}
        def gql(query, variables=None):
            if query.startswith('mutation'):
                self.assertEqual(records[news.DAILY]['status'], 'attempting')
                self.assertEqual(records[news.STATE]['status'], 'attempting')
                if outcome == 'timeout':
                    raise TimeoutError('uncertain response')
                return {'createPost': {'post': {'id': 'post1', 'status': 'scheduled'}}}
            return {'posts': {'edges': [{'node': {'id': 'post1', 'status': 'sent', 'externalLink': 'https://x.com/example'}}]}}
        with tempfile.TemporaryDirectory() as folder:
            original_path = news.Path
            with patch.object(news, 'Path', side_effect=lambda value: original_path(folder) / value), patch.object(news, 'graphic', side_effect=lambda path: path.write_bytes(b'image')), patch.object(p, 'get_file', return_value=(None, None)), patch.object(p, 'channel', return_value=('org', 'channel')), patch.object(p, 'request'), patch.object(p, 'put_file', side_effect=put), patch.object(p, 'gql', side_effect=gql):
                if outcome == 'timeout':
                    with self.assertRaises(TimeoutError):
                        news.main()
                else:
                    news.main()
        return records

    def test_shared_reservation_precedes_buffer_and_records_delivery(self):
        records = self.exercise_one_time('sent')
        self.assertEqual(records[news.DAILY]['status'], 'sent')
        self.assertEqual(records[news.DAILY]['post_id'], 'post1')
        self.assertIn('verified_at', records[news.DAILY])

    def test_uncertain_buffer_response_keeps_both_locks(self):
        records = self.exercise_one_time('timeout')
        self.assertEqual(records[news.DAILY]['status'], 'attempting')
        self.assertEqual(records[news.STATE]['status'], 'attempting')


if __name__ == '__main__':
    unittest.main()
