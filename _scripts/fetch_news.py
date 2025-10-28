import requests
import os
import yaml
import re
import jieba # 导入 jieba
from collections import Counter # 导入 Counter 来计数
from datetime import datetime, timedelta

# --- 1. 配置 ---

NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
if not NEWS_API_KEY:
    raise Exception("API key 'NEWS_API_KEY' not found. Please set it in GitHub Secrets.")

# API 和基本搜索词
NEWS_API_ENDPOINT = 'https://newsapi.org/v2/everything'
KEYWORDS = 'AI OR 人工智能 OR 人工智慧'
LANGUAGE = 'zh'

# --- 新的配置 ---
TARGET_ARTICLE_COUNT = 15      # 1. 最终主页显示 15 条
FETCH_POOL_SIZE = 50           # 2. 从昨天的 50 篇资讯中提取
TREND_SEARCH_DAYS = 10         # 3. 结合过去 10 天的热点
TREND_SEARCH_POOL_SIZE = 100   # 我们将获取 100 篇文章来分析热点
TOP_TRENDING_KEYWORDS_COUNT = 20 # 提取排名前 20 的热词
# --- 修改结束 ---

# Jekyll 的数据文件输出路径
OUTPUT_FILE_PATH = '_data/news.yml'

# 定义我们自己的 "停用词" 列表
# 这些词在分析热点时会被忽略，因为它们太常见了
CUSTOM_STOP_WORDS = {
    # 中文常见词
    '的', '了', '在', '是', '我', '你', '他', '她', '也', '和', '或', '都', '就', 
    '与', '及', '个', '为', '以', '中', '上', '下', '元', '月', '日', '年', '我们',
    '一个', '什么', '没有', '这个', '这些', '以及', '如何', '为什么', '可能', '进行',
    '表示', '成为', '推出', '发布', '出现', '使用', '基于', '通过', '据', '称',
    # 英文常见词
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'to', 'for', 'of', 'in', 'on', 
    'with', 'by', 'from', 'about', 'as', 'at', 'that', 'this', 'these', 'those',
    'and', 'or', 'but', 'if', 'what', 'when', 'where', 'how', 'which', 'who', 'whom',
    'will', 'can', 'not', 'it', 'its', 'they', 'their', 'we', 'our', 'you', 'your',
    # 过滤掉我们自己的搜索词
    'ai', '人工智能', '人工智慧'
}

# --- 2. 辅助函数 ---

def get_news_from_range(keywords, from_date, to_date, page_size, sort_by='popularity'):
    """一个通用的函数，用于从 NewsAPI 获取指定日期范围的新闻"""
    params = {
        'q': keywords,
        'from': from_date.strftime('%Y-%m-%d'),
        'to': to_date.strftime('%Y-%m-%d'),
        'language': LANGUAGE,
        'sortBy': sort_by,
        'pageSize': page_size,
        'apiKey': NEWS_API_KEY
    }
    print(f"  Fetching news from {params['from']} to {params['to']}...")
    try:
        response = requests.get(NEWS_API_ENDPOINT, params=params)
        response.raise_for_status()
        return response.json().get('articles', [])
    except requests.RequestException as e:
        print(f"  Error fetching news: {e}")
        return []

def extract_keywords(articles):
    """(Pass 1) 从文章标题中提取热词"""
    word_counts = Counter()
    
    for article in articles:
        title = article.get('title', '')
        if not title:
            continue
        
        # 使用 jieba.cut 来分词，它能同时处理中英文
        # .lower() 将所有词转为小写，以便统一计数
        words = jieba.cut(title.lower())
        
        for word in words:
            # 过滤掉停用词、数字、以及单个字符
            if word not in CUSTOM_STOP_WORDS and not word.isnumeric() and len(word) > 1:
                word_counts.update([word])
                
    # 返回最常见的 N 个词及其出现次数
    return word_counts.most_common(TOP_TRENDING_KEYWORDS_COUNT)

def score_article(article, trending_keywords):
    """(Pass 2) 根据热词给文章打分"""
    score = 0
    title = (article.get('title') or '').lower()
    description = (article.get('description') or '').lower()
    content = title + " " + description
    
    # trending_keywords 是一个列表，如 [('sora', 15), ('nvidia', 10)]
    for keyword, weight in trending_keywords:
        if keyword in content:
            # 如果文章内容包含了这个热词，就加上它的“热度”（即出现次数）
            score += weight
            
    return score

# --- 3. 主执行逻辑 ---

def main():
    
    # --- Pass 1: 发现过去10天的热词 ---
    print(f"PASS 1: Finding trending keywords from the last {TREND_SEARCH_DAYS} days...")
    
    today = datetime.now()
    # 我们要分析的是“昨天”之前的9天
    yesterday = today - timedelta(days=1)
    trend_start_date = today - timedelta(days=TREND_SEARCH_DAYS) 

    # 获取用于分析热词的文章
    trend_articles = get_news_from_range(
        KEYWORDS, 
        from_date=trend_start_date, 
        to_date=yesterday, # 注意：截止到昨天（不含今天）
        page_size=TREND_SEARCH_POOL_SIZE
    )
    
    if not trend_articles:
        print("  No articles found for trend analysis. Exiting.")
        return

    # 提取热词
    trending_keywords = extract_keywords(trend_articles)
    if not trending_keywords:
        print("  Could not extract any trending keywords. Exiting.")
        return
        
    print(f"  Top trending keywords found: {[k[0] for k in trending_keywords]}")

    
    # --- Pass 2: 获取并筛选昨天的资讯 ---
    print(f"\nPASS 2: Fetching and scoring {FETCH_POOL_SIZE} articles from yesterday...")

    # 1. 获取昨天的 50 篇文章
    yesterday_articles_pool = get_news_from_range(
        KEYWORDS,
        from_date=yesterday,
        to_date=yesterday,
        page_size=FETCH_POOL_SIZE
    )
    
    if not yesterday_articles_pool:
        print("  No articles found for yesterday. Exiting.")
        return

    # 2. 为这 50 篇文章打分
    scored_articles = []
    for article in yesterday_articles_pool:
        # 过滤掉无效文章
        if not article.get('title') or article['title'] == '[Removed]':
            continue
            
        score = score_article(article, trending_keywords)
        scored_articles.append((article, score)) # 将文章和分数绑定

    # 3. 按分数高低排序
    scored_articles.sort(key=lambda x: x[1], reverse=True)
    
    # 4. 提取分数最高的 15 篇
    top_articles = [article for article, score in scored_articles[:TARGET_ARTICLE_COUNT]]
    
    
    # --- Pass 3: 保存数据 ---
    print(f"\nPASS 3: Saving top {len(top_articles)} articles to {OUTPUT_FILE_PATH}...")

    processed_articles = []
    for article in top_articles:
        processed_articles.append({
            'title': article['title'],
            'description': article.get('description', ''),
            'url': article['url'],
            'source': article.get('source', {}).get('name', 'N/A'),
        })

    # 确保 _data 目录存在
    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    
    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(processed_articles, f, allow_unicode=True, sort_keys=False)

    print("Done.")

if __name__ == "__main__":
    main()
