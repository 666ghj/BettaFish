import unittest
from datetime import date, datetime
from unittest.mock import patch

from InsightEngine.tools.search import MediaCrawlerDB
from InsightEngine.utils.config import settings
from tests.insight_search_test_support import unbounded_weibo_rows


class InsightSearchDialectTests(unittest.TestCase):
    def _capture_platform_queries(self, dialect):
        db = MediaCrawlerDB()
        captured = []
        db._execute_query = lambda query, params=None: captured.append((query, params)) or []
        with patch.object(settings, "DB_DIALECT", dialect):
            db.search_topic_on_platform(
                "zhihu", "topic", "2026-01-01", "2026-01-02", limit=7
            )
        return captured

    def test_postgresql_uses_quoted_identifiers_bigint_and_named_parameters(self):
        captured = self._capture_platform_queries("postgresql")
        query, params = captured[0]

        self.assertIn('FROM "zhihu_content"', query)
        self.assertIn('CAST("created_time" AS BIGINT)', query)
        self.assertIn(':window_start', query)
        self.assertIn('LIMIT :limit', query)
        self.assertNotIn('%s', query)
        self.assertEqual(params['limit'], 7)

    def test_mysql_uses_backticks_signed_and_named_parameters(self):
        captured = self._capture_platform_queries("mysql")
        query, _params = captured[0]

        self.assertIn('FROM `zhihu_content`', query)
        self.assertIn('CAST(`created_time` AS SIGNED)', query)
        self.assertIn(':window_end', query)
        self.assertNotIn('%s', query)

    def test_douyin_date_filter_uses_seconds(self):
        db = MediaCrawlerDB()
        captured = []
        db._execute_query = lambda query, params=None: captured.append((query, params)) or []

        db.search_topic_on_platform(
            "douyin", "topic", "2026-09-01", "2026-09-01", limit=7
        )

        _query, params = captured[0]
        self.assertEqual(params["window_start"], int(datetime(2026, 9, 1).timestamp()))
        self.assertEqual(params["window_end"], int(datetime(2026, 9, 2).timestamp()))

    def test_platform_search_without_dates_attaches_unbounded_lineage(self):
        db = MediaCrawlerDB()
        db._execute_query = unbounded_weibo_rows

        response = db.search_topic_on_platform("weibo", "某热点事件")

        self.assertEqual(response.time_window, {"kind": "unbounded"})
        self.assertEqual(response.results_count, 1)
        self.assertEqual(
            response.results[0].provenance["time_window"], {"kind": "unbounded"}
        )
        self.assertEqual(response.results[0].provenance["primary_key"], "42")

    def test_platform_search_rejects_half_bounded_date_without_querying(self):
        db = MediaCrawlerDB()
        captured = []
        db._execute_query = lambda query, params=None: captured.append((query, params)) or []

        response = db.search_topic_on_platform(
            "weibo",
            "topic",
            start_date="2026-09-01",
        )

        self.assertIn("必须同时提供", response.error_message)
        self.assertEqual(captured, [])

    def test_platform_date_filter_applies_to_content_and_comment_tables(self):
        expected = {
            "bilibili": {"bilibili_video": "sec", "bilibili_video_comment": "sec"},
            "douyin": {"douyin_aweme": "sec", "douyin_aweme_comment": "sec"},
            "kuaishou": {"kuaishou_video": "ms", "kuaishou_video_comment": "ms"},
            "weibo": {"weibo_note": "str", "weibo_note_comment": "str"},
            "xhs": {"xhs_note": "ms", "xhs_note_comment": "ms"},
            "zhihu": {"zhihu_content": "sec", "zhihu_comment": "sec"},
            "tieba": {"tieba_note": "str", "tieba_comment": "str"},
        }
        seconds = (
            int(datetime(2026, 9, 1).timestamp()),
            int(datetime(2026, 9, 2).timestamp()),
        )

        for platform, table_kinds in expected.items():
            db = MediaCrawlerDB()
            captured = []
            db._execute_query = lambda query, params=None: captured.append((query, params)) or []
            db.search_topic_on_platform(
                platform,
                "topic",
                "2026-09-01",
                "2026-09-01",
            )
            self.assertEqual(len(captured), 2)
            for query, params in captured:
                table = next(name for name in table_kinds if name in query)
                self.assertIn(":window_start", query)
                self.assertIn(":window_end", query)
                kind = table_kinds[table]
                expected_bounds = (
                    (seconds[0] * 1000, seconds[1] * 1000)
                    if kind == "ms"
                    else ("2026-09-01", "2026-09-02")
                    if kind == "str"
                    else seconds
                )
                self.assertEqual(
                    (params["window_start"], params["window_end"]),
                    expected_bounds,
                )

    def test_postgresql_date_column_binds_python_dates(self):
        db = MediaCrawlerDB()
        config = {"time_col": "crawl_date", "time_type": "date_str"}

        with patch.object(settings, "DB_DIALECT", "postgresql"):
            _predicate, params = db._date_predicate(
                config, datetime(2026, 1, 1), datetime(2026, 1, 3)
            )

        self.assertEqual(params, {
            "window_start": date(2026, 1, 1),
            "window_end": date(2026, 1, 3),
        })

    def test_all_platform_date_boundaries_use_their_stored_units(self):
        db = MediaCrawlerDB()
        captured = []
        db._execute_query = lambda query, params=None: captured.append((query, params)) or []

        db.search_topic_by_date("topic", "2026-09-01", "2026-09-01", limit_per_table=3)

        by_table = {}
        for query, params in captured:
            table = next(name for name in (
                "bilibili_video", "douyin_aweme", "kuaishou_video", "weibo_note",
                "xhs_note", "zhihu_content", "tieba_note", "daily_news",
            ) if name in query)
            by_table[table] = params

        start = datetime(2026, 9, 1)
        end = datetime(2026, 9, 2)
        seconds = (int(start.timestamp()), int(end.timestamp()))
        milliseconds = (seconds[0] * 1000, seconds[1] * 1000)
        for table in ("bilibili_video", "douyin_aweme", "zhihu_content"):
            self.assertEqual(
                (by_table[table]["window_start"], by_table[table]["window_end"]),
                seconds,
            )
        for table in ("kuaishou_video", "xhs_note"):
            self.assertEqual(
                (by_table[table]["window_start"], by_table[table]["window_end"]),
                milliseconds,
            )
        for table in ("weibo_note", "tieba_note"):
            self.assertEqual(
                (by_table[table]["window_start"], by_table[table]["window_end"]),
                ("2026-09-01", "2026-09-02"),
            )
        self.assertEqual(
            (by_table["daily_news"]["window_start"], by_table["daily_news"]["window_end"]),
            (date(2026, 9, 1), date(2026, 9, 2)),
        )


if __name__ == "__main__":
    unittest.main()
