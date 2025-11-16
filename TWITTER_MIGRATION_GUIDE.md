# Twitter/X Scraping Migration Guide

## 🚨 URGENT: ntscraper is Broken

Your current Twitter implementation uses `ntscraper`, which **no longer works** as of 2025:
- Twitter blocked all Nitter instances
- Most Nitter servers have shut down
- The library is essentially non-functional

**You must migrate to a new solution immediately.**

---

## 📊 Recommended Solutions (Ranked for Your Use Case)

### Your Requirement: Monitor ~100 publishers daily

| Solution | Monthly Cost | Setup Time | Maintenance | Best For |
|----------|-------------|------------|-------------|----------|
| **1. Brand24** | $49-99 | 30 mins | None | ⭐⭐⭐⭐⭐ BEST OVERALL |
| **2. Apify API** | $8-20 | 1 hour | Minimal | ⭐⭐⭐⭐ Good value |
| **3. twikit** | $0 | 2-4 hours | 10-15 hrs/month | ⭐⭐⭐ Budget option |
| **4. Twitter API** | $200 | 1 week | None | ⭐⭐⭐⭐ If budget allows |

---

## Option 1: Brand24 (⭐ RECOMMENDED)

### Why This is Best for You:

✅ **Perfect fit for your needs:**
- Pre-built for monitoring publishers
- Monitors Twitter + Reddit + YouTube + news sites (multi-platform bonus!)
- Built-in sentiment analysis
- Alert system for breaking news
- Zero maintenance

✅ **Pricing:**
- $49/month (Individual plan)
- $99/month (Team plan with more features)
- 30-day free trial available

✅ **What you get:**
- Unlimited mentions tracking
- Real-time monitoring
- Sentiment analysis
- Share of voice metrics
- Email/Slack alerts
- Historical data
- API access

### Setup (15 minutes):

1. **Sign up for trial:**
   - Visit: https://brand24.com/
   - Start 30-day free trial (no credit card required)

2. **Add your publishers:**
   ```
   Projects > New Project > Add Keywords

   Keywords: @CNN, @FoxNews, @nytimes, @washingtonpost, ...
   (Add all 100 publisher handles)
   ```

3. **Configure alerts:**
   - Set up daily digest emails
   - Configure Slack/webhook integrations
   - Set sentiment thresholds

4. **Export data:**
   - Use their API for programmatic access
   - Or export to CSV/Excel

### API Integration (if you want to pull data into BettaFish):

```python
import requests

BRAND24_API_KEY = "your_api_key"
PROJECT_ID = "your_project_id"

# Get mentions
response = requests.get(
    f"https://api.brand24.com/mentions",
    headers={"Authorization": f"Bearer {BRAND24_API_KEY}"},
    params={
        "projectId": PROJECT_ID,
        "limit": 1000
    }
)

mentions = response.json()
```

---

## Option 2: Apify API

### Why Apify:

✅ **Pay-per-use pricing:**
- Only $0.25-0.30 per 1,000 tweets
- For 100 publishers × 10 tweets/day = ~$8-10/month
- Free tier includes $5 credit

✅ **Managed infrastructure:**
- They handle Twitter's anti-scraping
- Reliable even when Twitter changes
- No maintenance needed

### Setup (30 minutes):

1. **Sign up:**
   - Visit: https://apify.com/
   - Create free account ($5 credit included)

2. **Get API key:**
   - Dashboard > Settings > Integrations > API tokens
   - Copy your API key

3. **Add to .env:**
   ```bash
   APIFY_API_KEY=your_apify_api_key_here
   ```

4. **Use the new crawler:**
   ```python
   from MindSpider.DeepSentimentCrawling.western_platforms.twitter_crawler_v2 import TwitterCrawler

   # Initialize with Apify
   crawler = TwitterCrawler(method='apify')

   # Monitor publishers
   publishers = ['CNN', 'FoxNews', 'nytimes', ...]  # Your 100 publishers
   result = await crawler.monitor_publishers(
       publishers=publishers,
       tweets_per_publisher=10
   )
   ```

### Cost Calculation:

```
100 publishers × 10 tweets/day = 1,000 tweets/day
1,000 tweets/day × 30 days = 30,000 tweets/month
30,000 tweets ÷ 1,000 × $0.30 = $9/month

First month: FREE (using $5 credit)
Ongoing: ~$9-10/month
```

---

## Option 3: twikit (Free but Requires Work)

### Why twikit:

✅ **Completely free**
✅ **Actively maintained** (updated 2024-2025)
✅ **Works with current Twitter**

⚠️ **But requires:**
- Twitter account (risk of suspension)
- 10-15 hours/month maintenance
- Careful rate limiting

### Setup (2-4 hours):

1. **Create a Twitter scraper account:**
   - Use a separate email (not your personal account!)
   - Complete phone verification
   - Age the account for a few days before scraping

2. **Install twikit:**
   ```bash
   pip install twikit
   ```

3. **Add credentials to .env:**
   ```bash
   # For twikit
   TWITTER_USERNAME=your_scraper_account
   TWITTER_EMAIL=your_scraper_email
   TWITTER_PASSWORD=your_scraper_password
   ```

4. **Use the new crawler:**
   ```python
   from MindSpider.DeepSentimentCrawling.western_platforms.twitter_crawler_v2 import TwitterCrawler

   # Initialize with twikit
   crawler = TwitterCrawler(method='twikit', rate_limit_delay=15.0)

   # First run will login and save cookies
   await crawler.initialize()

   # Monitor publishers (will use saved cookies)
   publishers = ['CNN', 'FoxNews', 'nytimes', ...]
   result = await crawler.monitor_publishers(
       publishers=publishers,
       tweets_per_publisher=10
   )
   ```

### Rate Limiting (CRITICAL):

```python
# For 100 publishers, spread over 24 hours:
# 100 publishers × 15 seconds delay = 1,500 seconds = 25 minutes total
# Run once per day, you're well within safe limits

# Conservative schedule:
crawler = TwitterCrawler(
    method='twikit',
    rate_limit_delay=15.0  # 15 seconds between each publisher
)
```

### Maintenance Requirements:

- **Every 2-4 weeks**: Twitter changes their API
  - Watch for errors in logs
  - Update twikit: `pip install --upgrade twikit`
  - May need to re-login if cookies expire

- **Monthly**: Check account health
  - Ensure scraper account not suspended
  - Verify cookies still valid
  - Test with a few publishers

---

## Option 4: Official Twitter API

### Pricing:

- **Free tier**: 500 tweets/month (NOT enough for 100 publishers)
- **Basic tier**: $200/month for 15,000 tweets
  - 15,000 ÷ 100 publishers = 150 tweets/publisher/month
  - 150 ÷ 30 days = 5 tweets/publisher/day
  - **Verdict**: Might work, but tight

### Only recommended if:
- You have budget ($200/month)
- You need 100% reliability
- You want official, structured data

---

## Migration Steps

### Step 1: Choose Your Method

**Quick decision matrix:**

- **Have $50-100/month budget?** → Go with **Brand24**
- **Have $10-20/month budget?** → Go with **Apify**
- **Have $0 budget and technical skills?** → Go with **twikit**
- **Have $200/month budget and need max reliability?** → Official Twitter API

### Step 2: Install Dependencies

```bash
# For twikit (free)
pip install twikit

# For Apify (paid)
pip install httpx  # Already in requirements.txt

# Update all requirements
pip install -r requirements.txt
```

### Step 3: Update Configuration

Edit your `.env` file:

```bash
# Option A: twikit (free)
TWITTER_USERNAME=your_scraper_account
TWITTER_EMAIL=your_scraper_email
TWITTER_PASSWORD=your_scraper_password

# Option B: Apify (paid)
APIFY_API_KEY=your_apify_api_key

# Option C: Brand24 (paid)
BRAND24_API_KEY=your_brand24_api_key
BRAND24_PROJECT_ID=your_project_id
```

### Step 4: Update Your Code

**Old code (BROKEN):**
```python
from MindSpider.DeepSentimentCrawling.western_platforms import TwitterCrawler

crawler = TwitterCrawler(rate_limit_delay=10.0)  # Uses ntscraper
result = crawler.search_tweets(query='AI', mode='term', limit=10)
```

**New code (WORKING):**
```python
from MindSpider.DeepSentimentCrawling.western_platforms.twitter_crawler_v2 import TwitterCrawler
import asyncio

async def main():
    # Method 1: twikit (free)
    crawler = TwitterCrawler(method='twikit', rate_limit_delay=15.0)

    # Or Method 2: Apify (paid)
    # crawler = TwitterCrawler(method='apify')

    publishers = ['CNN', 'FoxNews', 'nytimes', 'washingtonpost', 'Reuters']

    result = await crawler.monitor_publishers(
        publishers=publishers,
        tweets_per_publisher=10
    )

    print(f"Collected {result['total_tweets']} tweets from {result['publishers_monitored']} publishers")

    await crawler.close()

asyncio.run(main())
```

### Step 5: Test

```bash
# Test with the new v2 crawler
python MindSpider/DeepSentimentCrawling/western_platforms/twitter_crawler_v2.py
```

### Step 6: Update Cron/Scheduler

If you're running automated monitoring:

```bash
# Old (broken)
# 0 0 * * * python monitor_twitter.py

# New (working) - run once daily
0 0 * * * python monitor_twitter_v2.py
```

---

## Production Deployment

### Daily Monitoring Script

Create `monitor_twitter_daily.py`:

```python
#!/usr/bin/env python3
import asyncio
from datetime import datetime
from loguru import logger
from MindSpider.DeepSentimentCrawling.western_platforms.twitter_crawler_v2 import TwitterCrawler

# Your 100 publishers
PUBLISHERS = [
    # Left-leaning
    'CNN', 'MSNBC', 'nytimes', 'washingtonpost', 'NPR',
    'guardian', 'HuffPost', 'Newsweek', 'TheDailyBeast', 'NBCNews',

    # Right-leaning
    'FoxNews', 'BreitbartNews', 'DailyWire', 'nypost', 'WSJ',
    'Washington Examiner', 'TheBlaze', 'OANN', 'NewsMax', 'DailyCaller',

    # Center
    'Reuters', 'AP', 'BBCNews', 'CBSNews', 'ABCNews',
    'axios', 'TheHill', 'politico', 'Forbes', 'Bloomberg',

    # Tech
    'TechCrunch', 'verge', 'WIRED', 'engadget', 'arstechnica',

    # Add your remaining 75 publishers...
]

async def monitor_daily():
    logger.info(f"Starting daily Twitter monitoring at {datetime.now()}")

    # Choose your method
    crawler = TwitterCrawler(
        method='twikit',  # or 'apify'
        rate_limit_delay=15.0  # 15 seconds between publishers
    )

    try:
        result = await crawler.monitor_publishers(
            publishers=PUBLISHERS,
            tweets_per_publisher=10  # 10 tweets per publisher per day
        )

        logger.info(f"✓ Monitoring complete:")
        logger.info(f"  Publishers: {result['publishers_monitored']}")
        logger.info(f"  Tweets collected: {result['total_tweets']}")

        # TODO: Save to database
        # save_to_database(result['tweets'])

    except Exception as e:
        logger.error(f"Monitoring failed: {e}")
    finally:
        await crawler.close()

if __name__ == "__main__":
    asyncio.run(monitor_daily())
```

Run daily with cron:
```bash
# Run at 2 AM every day
0 2 * * * /path/to/python /path/to/monitor_twitter_daily.py
```

---

## Comparison: Cost Over Time

### 1 Month:
- **Brand24**: $49-99 (trial = $0)
- **Apify**: ~$9-10 (first month free with credit)
- **twikit**: $0 + 10-15 hours of your time
- **Twitter API**: $200

### 6 Months:
- **Brand24**: $294-594
- **Apify**: ~$50-60
- **twikit**: $0 + 60-90 hours of maintenance
- **Twitter API**: $1,200

### 1 Year:
- **Brand24**: $588-1,188
- **Apify**: ~$100-120
- **twikit**: $0 + 120-180 hours of maintenance
- **Twitter API**: $2,400

---

## My Recommendation

### If you value your time and want reliability:
**Go with Brand24 ($49-99/month)**
- Zero maintenance
- Multi-platform (Twitter + Reddit + YouTube + news)
- Built-in analytics
- Start with 30-day free trial

### If you want lowest cost with decent reliability:
**Go with Apify (~$10/month)**
- Pay only for what you use
- Managed infrastructure
- Minimal maintenance

### If you have $0 budget and strong technical skills:
**Go with twikit (free)**
- But budget 10-15 hours/month for maintenance
- Use a throwaway Twitter account
- Be very careful with rate limiting

---

## Support

If you need help:
1. Check logs for specific errors
2. For twikit: https://github.com/d60/twikit/issues
3. For Apify: https://docs.apify.com/
4. For Brand24: https://brand24.com/support/

---

## FAQ

**Q: Can I use my personal Twitter account for twikit?**
A: No! Use a separate scraper account. Your personal account could get suspended.

**Q: Is twikit legal?**
A: It's against Twitter's ToS but not illegal. Use at your own risk. Brand24/Apify are safer as they handle the legal risk.

**Q: How long does it take to scrape 100 publishers?**
A: With 15-second delays: 100 × 15 = 1,500 seconds = 25 minutes. Run once daily.

**Q: What if my scraper account gets banned?**
A: With twikit: Create a new account. With Apify/Brand24: They handle it.

**Q: Can I scrape more than 10 tweets per publisher?**
A: Yes, but increases cost (Apify) or time (twikit). 10/day is usually sufficient.

**Q: Which method is most reliable?**
A: Brand24 > Twitter API > Apify > twikit

---

**Bottom Line**: For monitoring 100 publishers daily, **Brand24** offers the best balance of cost, reliability, and features. Try the free trial!
