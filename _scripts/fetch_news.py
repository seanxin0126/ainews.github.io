import requests
import os
import yaml
from datetime import datetime, timedelta

# --- 1. 配置 ---

# 从 GitHub Secrets 获取 API 密钥
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')

if not NEWS_API_KEY:
    raise Exception("API key 'NEWS_API_KEY' not found. Please set it in GitHub Secrets.")

# NewsAPI 配置
NEWS_API_ENDPOINT = 'https://newsapi.org/v2/everything'
# 搜索中文的 "AI" 或 "人工智能"
KEYWORDS = 'AI OR 人工智能 OR 人工智慧'
LANGUAGE = 'zh' # 只搜索简体中文和繁体中文
PAGE_SIZE = 9     # 直接获取9篇

# 获取前一天的日期 (YYYY-MM-DD 格式)
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

# Jekyll 的数据文件输出路径
OUTPUT_FILE_PATH = '_data/news.yml'

# --- 2. 主执行逻辑 ---

def main():
    print(f"Fetching {PAGE_SIZE} Chinese AI news for {yesterday}...")
    
    # 设置 API 请求参数
    params = {
        'q': KEYWORDS,
        'from': yesterday,
        'to': yesterday,
        'language': LANGUAGE,
        'sortBy': 'popularity', # 按热门程度排序（近似“影响力”）
        'pageSize': PAGE_SIZE,
        'apiKey': NEWS_API_KEY
    }

    try:
        response = requests.get(NEWS_API_ENDPOINT, params=params)
        response.raise_for_status() # 如果请求失败则抛出异常
        articles = response.json().get('articles', [])
    
    except requests.RequestException as e:
        print(f"Error fetching news: {e}")
        articles = []

    if not articles:
        print("No articles found.")
        return

    # --- 3. 处理数据 ---
    processed_articles = []
    print(f"Processing {len(articles)} articles...")
    
    for article in articles:
        # 过滤掉已删除或没有标题的文章
        if not article.get('title') or article['title'] == '[Removed]':
            continue

        processed_articles.append({
            'title': article['title'],
            'description': article.get('description', ''), # 描述可能为空
            'url': article['url'],
            'source': article.get('source', {}).get('name', 'N/A'), # 来源名称
        })

    # --- 4. 保存数据到 _data/news.yml ---
    
    # 确保 _data 目录存在
    os.makedirs(os.path.dirname(OUTPUT_FILE_PATH), exist_ok=True)
    
    # 将结果写入 Jekyll 的 _data 文件
    # 使用 allow_unicode=True 来正确保存中文字符
    print(f"Saving {len(processed_articles)} articles to {OUTPUT_FILE_PATH}...")
    with open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(processed_articles, f, allow_unicode=True, sort_keys=False)

    print("Done.")

if __name__ == "__main__":
    main()
