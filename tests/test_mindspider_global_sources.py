import asyncio

from MindSpider.BroadTopicExtraction.get_today_news import NewsCollector
from MindSpider.source_providers import (
    BlueskySourceProvider,
    GitHubSourceProvider,
    HackerNewsSourceProvider,
    MastodonSourceProvider,
    RedditApiSourceProvider,
    RedditSourceProvider,
    SourceProviderError,
    XApiSourceProvider,
    YouTubeDataSourceProvider,
    YouTubeSearchSourceProvider,
)


class _FakeDb:
    def __init__(self):
        self.saved = []
    def close(self):
        pass
    def save_daily_news(self, news_data, crawl_date=None):
        self.saved.extend(news_data)
        return len(news_data)


def test_hackernews_provider_normalizes_public_api(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: {
        'hits': [{'title': 'HN Topic', 'url': 'https://example.com/hn', 'story_text': 'body', 'created_at': '2026-06-13T00:00:00Z'}]
    })
    items = HackerNewsSourceProvider().collect(['ai'], max_results_per_query=1)
    assert items[0].title == 'HN Topic'
    assert items[0].source_provider == 'hackernews'
    assert items[0].source_platform == 'hackernews'


def test_github_provider_normalizes_repositories(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: {
        'items': [{'full_name': 'owner/repo', 'html_url': 'https://github.com/owner/repo', 'description': 'desc', 'updated_at': '2026-06-13T00:00:00Z'}]
    })
    items = GitHubSourceProvider().collect(['ai'], max_results_per_query=1)
    assert items[0].title == 'owner/repo'
    assert items[0].source_provider == 'github'
    assert items[0].source_platform == 'github_repositories'


def test_reddit_provider_uses_public_search_without_login(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: {
        'data': {'children': [{'data': {'title': 'Reddit Topic', 'permalink': '/r/test/comments/1/topic', 'selftext': 'discussion', 'created_utc': 1781308800}}]}
    })
    items = RedditSourceProvider(subreddits=['LocalLLaMA']).collect(['ai'], max_results_per_query=1)
    assert items[0].title == 'Reddit Topic'
    assert items[0].url.startswith('https://www.reddit.com/')
    assert items[0].source_provider == 'reddit'


def test_reddit_api_requires_credentials():
    try:
        RedditApiSourceProvider(client_id=None, client_secret=None).collect(['ai'], max_results_per_query=1)
    except SourceProviderError as exc:
        assert 'REDDIT_CLIENT_ID' in str(exc)
    else:
        raise AssertionError('expected SourceProviderError')


def test_reddit_api_normalizes_oauth_results(monkeypatch):
    calls = []
    def fake_post(*args, **kwargs):
        return {'access_token': 'tok'}
    def fake_get(url, *args, **kwargs):
        calls.append(url)
        return {'data': {'children': [{'data': {'title': 'API Reddit', 'permalink': '/r/test/comments/2/topic', 'selftext': 'api body'}}]}}
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_post_form', fake_post)
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', fake_get)
    items = RedditApiSourceProvider(client_id='id', client_secret='secret').collect(['ai'], max_results_per_query=1)
    assert items[0].source_provider == 'reddit-api'
    assert 'oauth.reddit.com' in calls[0]


def test_youtube_search_uses_configured_search_provider(monkeypatch):
    seen = {}
    def fake_collect(self, queries, max_results_per_query=10):
        seen['queries'] = list(queries)
        from MindSpider.source_providers import SourceItem
        return [SourceItem(title='Video', url='https://youtube.com/watch?v=x', source_provider='searxng', source_platform='web_search')]
    monkeypatch.setattr('MindSpider.source_providers.global_sources.SearchBackedSourceProvider.collect', fake_collect)
    items = YouTubeSearchSourceProvider('searxng').collect(['ai'], max_results_per_query=1)
    assert seen['queries'][0].startswith('site:youtube.com/watch ')
    assert items[0].source_provider == 'youtube'
    assert items[0].source_platform == 'youtube_search'


def test_youtube_data_requires_api_key():
    try:
        YouTubeDataSourceProvider(api_key=None).collect(['ai'], max_results_per_query=1)
    except SourceProviderError as exc:
        assert 'YOUTUBE_DATA_API_KEY' in str(exc)
    else:
        raise AssertionError('expected SourceProviderError')


def test_youtube_data_normalizes_results(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: {
        'items': [{'id': {'videoId': 'abc'}, 'snippet': {'title': 'YT Topic', 'description': 'desc', 'publishedAt': '2026-06-13T00:00:00Z'}}]
    })
    items = YouTubeDataSourceProvider(api_key='key').collect(['ai'], max_results_per_query=1)
    assert items[0].source_provider == 'youtube-data'
    assert items[0].url.endswith('abc')


def test_bluesky_provider_normalizes_public_posts(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: {
        'posts': [{'uri': 'at://did/app.bsky.feed.post/xyz', 'author': {'handle': 'user.bsky.social'}, 'record': {'text': 'Blue topic\nbody', 'createdAt': '2026-06-13T00:00:00Z'}}]
    })
    items = BlueskySourceProvider().collect(['ai'], max_results_per_query=1)
    assert items[0].source_provider == 'bluesky'
    assert 'bsky.app/profile/user.bsky.social/post/xyz' in items[0].url


def test_bluesky_provider_can_use_app_password_session(monkeypatch):
    seen = {}
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_post_json', lambda *args, **kwargs: {'accessJwt': 'jwt'})
    def fake_get(url, *args, **kwargs):
        seen['headers'] = kwargs.get('headers')
        return {'posts': [{'uri': 'at://did/app.bsky.feed.post/xyz', 'author': {'handle': 'user.bsky.social'}, 'record': {'text': 'Blue topic'}}]}
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', fake_get)
    items = BlueskySourceProvider(identifier='user.bsky.social', app_password='secret').collect(['ai'], max_results_per_query=1)
    assert seen['headers']['Authorization'] == 'Bearer jwt'
    assert items[0].source_provider == 'bluesky'


def test_mastodon_provider_normalizes_hashtag_timeline(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: [
        {'content': '<p>Mastodon topic</p>', 'url': 'https://mastodon.social/@u/1', 'created_at': '2026-06-13T00:00:00Z', 'account': {'acct': 'u'}}
    ])
    items = MastodonSourceProvider(instance='mastodon.social').collect(['ai'], max_results_per_query=1)
    assert items[0].source_provider == 'mastodon'
    assert items[0].source_platform == 'mastodon'


def test_x_api_requires_bearer_token():
    try:
        XApiSourceProvider(bearer_token=None).collect(['ai'], max_results_per_query=1)
    except SourceProviderError as exc:
        assert 'X_BEARER_TOKEN' in str(exc)
    else:
        raise AssertionError('expected SourceProviderError')


def test_x_api_normalizes_results(monkeypatch):
    monkeypatch.setattr('MindSpider.source_providers.global_sources._json_get', lambda *args, **kwargs: {
        'data': [{'id': '123', 'text': 'X topic', 'created_at': '2026-06-13T00:00:00Z'}]
    })
    items = XApiSourceProvider(bearer_token='token').collect(['ai'], max_results_per_query=1)
    assert items[0].source_provider == 'x-api'
    assert items[0].url.endswith('/123')


def test_news_collector_collects_global_sources(monkeypatch):
    monkeypatch.setattr('MindSpider.BroadTopicExtraction.get_today_news.BlueskySourceProvider.collect', lambda self, queries, max_results_per_query=10: [
        __import__('MindSpider.source_providers', fromlist=['SourceItem']).SourceItem(title='Blue Topic', url='https://bsky.app', source_provider='bluesky', source_platform='bluesky')
    ])
    collector = NewsCollector(source_mode='localized', provider='searxng', queries=['ai'], db_manager=_FakeDb())
    result = asyncio.run(collector.collect_and_save_news(sources=['bluesky']))
    assert result['success']
    assert result['saved_count'] == 1
    assert result['news_list'][0]['source_provider'] == 'bluesky'


def test_key_backed_sources_fail_closed_in_collector():
    collector = NewsCollector(source_mode='localized', provider='searxng', queries=['ai'], db_manager=_FakeDb())
    result = asyncio.run(collector.collect_and_save_news(sources=['youtube-data']))
    assert not result['success']
    assert 'YOUTUBE_DATA_API_KEY' in result['error']
