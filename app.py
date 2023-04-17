# from fastapi import FastAPI
# import httpx
# from bs4 import BeautifulSoup

# app = FastAPI()

# class NewsItem:
#     def __init__(self, title: str, link: str, pub_date: str):
#         self.title = title
#         self.link = link
#         self.pub_date = pub_date

#     def __repr__(self):
#         return f"<NewsItem(title='{self.title}', link='{self.link}', pub_date='{self.pub_date}')>"

# class GoogleNewsRSS:
#     def __init__(self, rss_feed: str):
#         self.rss_feed = rss_feed
#         self.news_items = self.parse_rss_feed()

#     def parse_rss_feed(self):
#         soup = BeautifulSoup(self.rss_feed, "html.parser")
#         items = soup.find_all("item")
#         news_items = []

#         for item in items:
#             title = item.title.text
#             link = item.link.text
#             pub_date = item.pubdate.text
#             news_items.append(NewsItem(title, link, pub_date))

#         return news_items

#     def to_dict(self):
#         return [item.__dict__ for item in self.news_items]

# @app.get("/search_news/")
# async def search_news(query: str):
#     url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
#     async with httpx.AsyncClient() as client:
#         response = await client.get(url)

#     if response.status_code == 200:
#         google_news_rss = GoogleNewsRSS(response.text)
#         feedData = google_news_rss.parse_rss_feed()
#         return feedData[0].title
#     else:
#         return {"error": "Failed to fetch news"}

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


import os, html
import base64
from functools import partial
import openai
from fastapi import FastAPI
import httpx
from bs4 import BeautifulSoup
import asyncio
from urllib.parse import unquote
app = FastAPI()

# Add your OpenAI API key here
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY

class NewsItem:
    def __init__(self, title: str, link: str, pub_date: str):
        self.title = title
        self.link = link
        self.pub_date = pub_date

    def __repr__(self):
        return f"<NewsItem(title='{self.title}', link='{self.link}', pub_date='{self.pub_date}')>"

    def to_dict(self):
        return {
            "title": self.title,
            "link": self.link,
            "pub_date": self.pub_date,
        }

# class GoogleNewsRSS:
#     def __init__(self, rss_feed):
#         self.rss_feed = rss_feed
#         self.news_items = self.parse_rss_feed()

#     def parse_rss_feed(self):
#         soup = BeautifulSoup(self.rss_feed, "html.parser")
#         items = soup.find_all("item")
#         news_items = []

#         for item in items:
#             title = item.title.text
#             link = item.guid.text if item.guid else item.link.text
#             print(link)
            
            
#             pub_date = item.pubdate.text

#             # Check if the link is encoded in base64
#             if link.startswith("data:text/plain;base64,"):
#                 # Decode the link
#                 decoded_link = base64.b64decode(link[25:]).decode('utf-8')
#             else:
#                 decoded_link = link

#             news_items.append(NewsItem(title, decoded_link, pub_date))

#         return news_items



#     def to_dict(self):
#         return [item.__dict__ for item in self.news_items]

class GoogleNewsRSS:
    def __init__(self, rss_feed):
        self.channel = {}
        self.items = []
        self.decode_rss_feed(rss_feed)

    def decode_rss_feed(self, rss_feed):
        decoded_feed = html.unescape(rss_feed)
        decoded_feed = decoded_feed.encode('ascii', 'ignore').decode('ascii')
        decoded_feed = decoded_feed.replace("&amp;", "&")

        for item in decoded_feed.split("<item>")[1:]:
            title = self.extract_tag_value(item, "title")
            link = self.decode_link(self.extract_tag_value(item, "link"))
            pub_date = self.extract_tag_value(item, "pubDate")
            guid = self.decode_guid(self.extract_tag_value(item, "guid"))
            description = self.extract_tag_value(item, "description")

            self.items.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "guid": guid,
                "description": description
            })

        self.channel["title"] = self.extract_tag_value(decoded_feed, "title")
        self.channel["link"] = self.decode_link(self.extract_tag_value(decoded_feed, "link"))
        self.channel["language"] = self.extract_tag_value(decoded_feed, "language")
        self.channel["description"] = self.extract_tag_value(decoded_feed, "description")

    @staticmethod
    def extract_tag_value(xml_string, tag_name):
        start_tag = "<{}>".format(tag_name)
        end_tag = "</{}>".format(tag_name)
        start_index = xml_string.find(start_tag) + len(start_tag)
        end_index = xml_string.find(end_tag)
        return xml_string[start_index:end_index].strip()

    @staticmethod
    def decode_link(link):
        return base64.b64decode(link).decode('utf-8')

    @staticmethod
    def decode_guid(guid):
        if guid:
            guid = guid.strip()
            if guid.startswith("http"):
                guid = base64.b64decode(guid).decode('utf-8')
        return guid
async def score_news_item(news_item: NewsItem):
    prompt = f"Rate the credibility of the following news item from 1 (least credible) to 10 (most credible):\n\nTitle: {news_item.title}\nLink: {news_item.link}\nPublished Date: {news_item.pub_date}\n\nScore: "
    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, partial(openai.Completion.create,
        engine="text-davinci-002",
        prompt=prompt,
        n=1,
        max_tokens=5,
        stop=None,
        temperature=0.5,
    ))

    try:
        score = float(response.choices[0].text.strip())
    except ValueError:
        score = 0
    return score

@app.get("/search_news/")
async def search_news(query: str, min_score: float = 5.0):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code == 200:
        google_news_rss = GoogleNewsRSS(response.text)
        # tasks = [score_news_item(news_item) for news_item in google_news_rss.news_items]

        # scores = await asyncio.gather(*tasks)

        # scored_news_items = []
        # for news_item, score in zip(google_news_rss.news_items, scores):
        #     if score >= min_score:
        #         scored_news_items.append({"news_item": news_item.to_dict(), "score": score})

        return google_news_rss
    else:
        return {"error": "Failed to fetch news"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
