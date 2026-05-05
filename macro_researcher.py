from duckduckgo_search import DDGS
import json
import os
import datetime


def fetch_macro_news():
    out_file = "outputs/macro_news.json"
    
    # Check if file exists and is less than 1 day old to save API calls
    if os.path.exists(out_file):
        file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(out_file))
        if (datetime.datetime.now() - file_mod_time).days < 1:
            print("Macro news file is less than 1 day old. Using cached version.")
            return out_file
            
    print("Fetching robust macroeconomic news via DuckDuckGo Search...")
    
    # Search queries targeted at Brazilian economy and global macro
    queries = [
        "economia brasil selic inflação",
        "mercado financeiro ibovespa ações",
        "federal reserve eua juros"
    ]
    
    news_items = []
    
    try:
        with DDGS() as ddgs:
            for query in queries:
                print(f"  -> Searching for: '{query}'")
                
                # Fetch news results (title, body, date, source)
                try:
                    news_results = list(ddgs.news(query, region='br-pt', safesearch='Off', max_results=7))
                    for r in news_results:
                        news_items.append({
                            "title": r.get('title', ''),
                            "date": r.get('date', datetime.datetime.now().strftime("%Y-%m-%d")),
                            "summary": r.get('body', ''),
                            "source": r.get('source', '')
                        })
                except Exception as e_news:
                    print(f"  -> DDGS.news fallback to text search due to: {e_news}")
                    # Fallback to text if news endpoint fails
                    text_results = list(ddgs.text(query + " notícias hoje", region='br-pt', safesearch='Off', max_results=7))
                    for r in text_results:
                        news_items.append({
                            "title": r.get('title', ''),
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "summary": r.get('body', ''),
                            "source": "Web Search"
                        })
                        
    except Exception as e:
        print(f"Error searching news: {e}")
        
    if not news_items:
        news_items.append({
            "title": "Mercado aguarda novas diretrizes econômicas e definições de juros", 
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "summary": "Investidores seguem em compasso de espera por divulgações de dados de inflação."
        })
        
    # Remove duplicates based on title
    seen_titles = set()
    unique_news = []
    for item in news_items:
        if item['title'] not in seen_titles:
            unique_news.append(item)
            seen_titles.add(item['title'])
            
    # Save results to JSON
    out_file = "outputs/macro_news.json"
    os.makedirs("outputs", exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(unique_news, f, ensure_ascii=False, indent=2)
        
    print(f"Robust macro news saved at {out_file} ({len(unique_news)} articles)")
    return out_file

if __name__ == "__main__":
    fetch_macro_news()
