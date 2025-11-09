# BettaFish - File Location Reference for USA Adaptation

## Chinese Platforms Crawler Files

### Media Platform Crawlers
```
/home/user/BettaFish/MindSpider/DeepSentimentCrawling/MediaCrawler/
├── media_platform/
│   ├── weibo/                  # Weibo (微博)
│   │   ├── client.py
│   │   ├── core.py            ← Main crawler logic
│   │   ├── field.py
│   │   ├── login.py
│   │   ├── exception.py
│   │   └── help.py
│   │
│   ├── douyin/                 # Douyin/TikTok China (抖音)
│   │   ├── client.py
│   │   ├── core.py            ← Main crawler logic
│   │   ├── field.py
│   │   ├── login.py
│   │   ├── exception.py
│   │   └── help.py
│   │
│   ├── xhs/                    # Xiaohongshu (小红书)
│   │   ├── client.py
│   │   ├── core.py            ← Main crawler logic
│   │   ├── field.py
│   │   ├── login.py
│   │   ├── exception.py
│   │   ├── help.py
│   │   ├── extractor.py
│   │   └── secsign.py
│   │
│   ├── bilibili/               # Bilibili (B站)
│   │   ├── client.py
│   │   ├── core.py            ← Main crawler logic
│   │   ├── field.py
│   │   ├── login.py
│   │   ├── exception.py
│   │   └── help.py
│   │
│   ├── kuaishou/               # Kuaishou (快手)
│   │   ├── client.py
│   │   ├── core.py            ← Main crawler logic
│   │   ├── field.py
│   │   ├── login.py
│   │   ├── exception.py
│   │   ├── help.py
│   │   └── graphql.py
│   │
│   ├── zhihu/                  # Zhihu (知乎)
│   │   ├── client.py
│   │   ├── core.py            ← Main crawler logic
│   │   ├── field.py
│   │   ├── login.py
│   │   ├── exception.py
│   │   └── help.py
│   │
│   └── tieba/                  # Tieba (贴吧)
│       ├── client.py
│       ├── core.py            ← Main crawler logic
│       ├── field.py
│       ├── login.py
│       └── help.py
│
├── main.py                     ⭐ CRITICAL - CrawlerFactory.CRAWLERS dict (line 32-40)
├── model/                      # Data models for crawling
│   ├── m_weibo.py
│   ├── m_douyin.py
│   ├── m_bilibili.py
│   ├── m_kuaishou.py
│   ├── m_xiaohongshu.py
│   ├── m_zhihu.py
│   └── m_baidu_tieba.py
│
├── database/
│   └── models.py              ⭐ CRITICAL - All database table definitions
│
├── store/                      # Data persistence
│   ├── weibo/
│   ├── douyin/
│   ├── bilibili/
│   ├── kuaishou/
│   ├── xhs/
│   ├── zhihu/
│   └── tieba/
│
└── config/
    ├── weibo_config.py
    ├── dy_config.py
    ├── xhs_config.py
    ├── bilibili_config.py
    ├── ks_config.py
    ├── zhihu_config.py
    └── tieba_config.py
```

---

## Prompt Files (System Instructions) - NEED COMPLETE TRANSLATION

### InsightEngine
```
/home/user/BettaFish/InsightEngine/
├── prompts/
│   └── prompts.py                              📄 630 lines - CRITICAL
│       ├── Line 40:    Platform names hardcoded in description
│       ├── Line 136-167: SYSTEM_PROMPT_REPORT_STRUCTURE
│       │                  "你是一位专业的舆情分析师和报告架构师"
│       ├── Line 170-267: SYSTEM_PROMPT_FIRST_SEARCH
│       │                  - 247-253: Platform-specific language examples
│       │                  - 241-246: Search term examples (Chinese)
│       ├── Line 269-347: SYSTEM_PROMPT_FIRST_SUMMARY
│       ├── Line 349-421: SYSTEM_PROMPT_REFLECTION
│       │                  - 403-412: Search term optimization examples
│       └── Line 423-512: SYSTEM_PROMPT_REFLECTION_SUMMARY
│
└── tools/
    └── search.py                               📄 800+ lines - CRITICAL
        ├── Line 1-50:    Tool description (Chinese)
        ├── Line 130-250: search_hot_content() - Platform table mapping
        ├── Line 260-350: search_topic_globally() - Database queries
        ├── Line 360-450: search_topic_by_date() - Date-based queries
        ├── Line 460-550: get_comments_for_topic() - Comment extraction
        └── Line 560-650: search_topic_on_platform() - Platform-specific search
```

### MediaEngine
```
/home/user/BettaFish/MediaEngine/
└── prompts/
    └── prompts.py                              📄 450 lines - CRITICAL
        ├── Line 40:      Platform list: "bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba"
        └── ALL system prompts use Chinese instructions
```

### QueryEngine
```
/home/user/BettaFish/QueryEngine/
└── prompts/
    └── prompts.py                              📄 450 lines - CRITICAL
        ├── Line 40:      Platform list parameter definition
        ├── Line 150-177: Tool descriptions
        └── ALL examples use Chinese queries
```

### ReportEngine
```
/home/user/BettaFish/ReportEngine/
├── prompts/
│   └── prompts.py                              📄 136 lines
│       ├── Line 45-70:   Template selection system prompt
│       └── Line 73-135:  HTML generation system prompt
│
└── report_template/                            📄 6 markdown files - NEED CONTEXT UPDATE
    ├── 企业品牌声誉分析报告模板.md            → Brand Reputation Analysis
    ├── 市场竞争格局舆情分析报告模板.md        → Market Competition Analysis
    ├── 日常或定期舆情监测报告模板.md          → Daily Monitoring Report
    ├── 特定政策或行业动态舆情分析报告.md      → Policy/Industry Dynamics
    ├── 社会公共热点事件分析报告模板.md        → Public Event Analysis
    └── 突发事件与危机公关舆情报告模板.md      → Crisis Management Report
```

---

## Configuration Files

### Main Configuration
```
/home/user/BettaFish/
├── config.py                                   📄 104 lines - CRITICAL
│   ├── Line 23-39:   Flask server config
│   ├── Line 32-39:   Database config
│   ├── Line 41-73:   LLM API configurations
│   │   ├── INSIGHT_ENGINE_MODEL_NAME: "kimi-k2-0711-preview"
│   │   ├── MEDIA_ENGINE_MODEL_NAME: "gemini-2.5-pro"
│   │   ├── QUERY_ENGINE_MODEL_NAME: "deepseek-reasoner"
│   │   ├── FORUM_HOST_MODEL_NAME: "Qwen/Qwen3-235B..."
│   │   └── KEYWORD_OPTIMIZER_MODEL_NAME: "Qwen/Qwen3-30B..."
│   ├── Line 74-81:   Network tools (Tavily, Bocha)
│   └── Line 82-93:   Search limits and timeouts
│
└── .env.example                                📄 81 lines
    └── Configuration template for all services
```

### MindSpider Configuration
```
/home/user/BettaFish/MindSpider/
└── config.py                                   📄 36 lines
    └── Database and LLM config for MindSpider module
```

---

## Sentiment Analysis Models

```
/home/user/BettaFish/SentimentAnalysisModel/
├── WeiboMultilingualSentiment/
│   ├── README.md                               # Supports 22 languages
│   ├── predict.py                              # 100+ lines
│   │   ├── Model: tabularisai/multilingual-sentiment-analysis
│   │   ├── Line 40-43: Sentiment map (5-level)
│   │   │   0: "非常负面", 1: "负面", 2: "中性", 3: "正面", 4: "非常正面"
│   │   └── Can be reused for English ✓
│   │
├── WeiboSentiment_MachineLearning/
│   ├── svm_train.py
│   ├── xgboost_train.py
│   ├── bayes_train.py
│   ├── lstm_train.py
│   ├── bert_train.py
│   └── predict.py
│   │   └── Chinese-optimized models - Not suitable for English
│
├── WeiboSentiment_Finetuned/
│   ├── GPT2-Lora/
│   ├── BertChinese-Lora/
│   └── GPT2-AdapterTuning/
│   │   └── Chinese-specific fine-tuning
│
├── WeiboSentiment_SmallQwen/
│   ├── qwen3_lora_universal.py
│   ├── qwen3_embedding_universal.py
│   └── predict_universal.py
│   │   └── Qwen3 Chinese model - Not suitable for English
│
└── BertTopicDetection_Finetuned/
    ├── train.py
    └── predict.py
        └── Topic detection - Language independent, can reuse
```

---

## Database Schema Files

```
/home/user/BettaFish/MindSpider/DeepSentimentCrawling/MediaCrawler/
└── database/models.py                          📄 150+ lines (extends)
    ├── BilibiliVideo, BilibiliVideoComment, BilibiliUpInfo
    ├── BilibiliContactInfo, BilibiliUpDynamic
    ├── DouyinAweme, DouyinAwemeComment, DyCreator
    ├── WeiboContent, WeiboComment, WeiboUser
    ├── KuaishouContent, KuaishouComment
    ├── XiaoHongShuNote, XiaoHongShuComment, XiaoHongShuUser
    ├── ZhihuQuestion, ZhihuAnswer, ZhihuComment
    └── TiebaThread, TiebaPost
```

---

## Code Comments & Documentation (95% in Chinese)

### Heavily Commented Files (Require Translation)
```
/home/user/BettaFish/
├── MindSpider/
│   └── DeepSentimentCrawling/
│       └── MediaCrawler/
│           ├── main.py                         # Line 1-10: Declaration + line 14: "微博爬虫主流程代码"
│           ├── media_platform/
│           │   ├── weibo/core.py               # Line 1-50: All Chinese comments
│           │   ├── douyin/core.py              # Line 1-50: All Chinese comments
│           │   ├── xhs/core.py                 # Line 1-50: All Chinese comments
│           │   ├── bilibili/core.py            # Line 1-50: All Chinese comments
│           │   ├── kuaishou/core.py            # Line 1-50: All Chinese comments
│           │   ├── zhihu/core.py               # Line 1-50: All Chinese comments
│           │   └── tieba/core.py               # Line 1-50: All Chinese comments
│           │
│           └── database/models.py              # Class definitions in English but Chinese examples
│
├── InsightEngine/
│   ├── tools/
│   │   ├── search.py                           # Line 1-100: Chinese documentation
│   │   ├── sentiment_analyzer.py               # Comments in Chinese
│   │   └── keyword_optimizer.py                # Comments in Chinese
│   │
│   └── agent.py                                # Comments in Chinese
│
├── MediaEngine/                                # All prompts and logic in Chinese
├── QueryEngine/                                # All prompts and logic in Chinese
├── ReportEngine/                               # All prompts and logic in Chinese
└── ForumEngine/                                # Logic and messages in Chinese
```

---

## Key Lines to Change - Summary Table

| File | Line(s) | Current | Change To |
|------|---------|---------|-----------|
| main.py | 32-40 | CrawlerFactory.CRAWLERS (7 platforms) | Add 7 new crawlers |
| models.py | 1-300 | 7 platform table definitions | Add 7 new table definitions |
| search.py | 18-24 | Tool descriptions (Chinese) | Translate to English |
| search.py | 150-250 | Platform table mappings | Update for new platforms |
| config.py | 41-73 | Chinese-optimized LLM models | Switch to English models |
| config.py | 32-39 | Database charset comment | No change needed (UTF-8mb4) |
| prompts.py (all) | 40 | Platform list | Update all 4 prompt files |
| prompts.py (all) | Entire | Chinese instructions | Complete translation/rewrite |
| All .py files | Throughout | Chinese comments | Translate to English |

---

## Recommended Implementation Order

### Phase 1: Setup (Week 1)
1. Fork/branch the project
2. Create new crawler directories for 7 USA platforms
3. Set up new database models
4. Add API key configuration

### Phase 2: Core Crawlers (Weeks 2-4)
1. Implement Twitter API v2 crawler
2. Implement Reddit API crawler
3. Implement Facebook Graph API crawler
4. Create abstraction layer in search tools

### Phase 3: Prompts & Language (Weeks 5-6)
1. Translate InsightEngine prompts
2. Translate MediaEngine prompts
3. Translate QueryEngine prompts
4. Translate ReportEngine prompts
5. Update system prompt examples

### Phase 4: Remaining Crawlers (Weeks 7-8)
1. Implement Instagram, YouTube, LinkedIn crawlers
2. Implement TikTok US crawler

### Phase 5: Sentiment & Polish (Weeks 9-10)
1. Set up sentiment analysis for English
2. Fine-tune on USA social media data
3. Translate all code comments
4. Update error messages

### Phase 6: Testing & Documentation (Weeks 11-16)
1. Integration testing for each platform
2. Create USA-specific documentation
3. Update README and guides
4. Performance optimization

