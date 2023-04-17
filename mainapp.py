from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import feedparser
import time
import sys
import pandas as pd
import re
import urllib
import urllib.request as ur
import argparse
import bs4
import openai
from typing import List, Optional
import httpx
import asyncio
from functools import partial

app = FastAPI()

openai.api_key = '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'

class Article(BaseModel):
    title: str
    link: str
    pub_date: str
    description: str
    source: str
    query: str
    alexa_rank: Optional[str] = None

async def generate_text(prompt):
    loop = asyncio.get_event_loop()
    prompt = prompt + " " + " ".join([f" {i}" for i in range(10)])
    response = await loop.run_in_executor(None, partial(openai.ChatCompletion.create, model="gpt-3.5-turbo", messages=[{"role": "user", "content":prompt}], max_tokens=50, n=1, stop=None, temperature=0.5))
    data = response
    if "choices" not in data:
        print(f"Error: {data}")
        return ""
    return data["choices"][0]["message"]["content"].strip()

class NewsScraper:
    def __init__(self, queries, language="en", locations=[]):
        self.base_url = 'https://news.google.com/rss/search?q='
        self.queries = queries
        self.language = language
        self.locations = locations
        self.d = []

    # Get Alexa Rank - remember it only works from USA so you need a proxy
    def getMetrics(self, url):
        cleanDomain = '/'.join(url.split('/')[:3])
        try:
            alexa_rank = bs4.BeautifulSoup(ur.urlopen("http://data.alexa.com/data?cli=10&dat=s&url="+ url), "xml").find("REACH")["RANK"]
        except:
            alexa_rank = None
        return alexa_rank

    # HTML cleanup function
    def cleanhtml(self, raw_html):
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext

    # Access the feed and store data in d
    def readFeed(self, url, query):
        feed = feedparser.parse(url)
        # Loop items in the feed
        for post in feed.entries:
            title = post.title
            link = post.link
            # Converting published date to aaaa/mm/dd
            pubDate = "%d/%02d/%02d" % (post.published_parsed.tm_year,\
                post.published_parsed.tm_mon, \
                post.published_parsed.tm_mday)

            description = self.cleanhtml(post.summary)
            source = post.source.title
            # Get Alexa Rank
            alexa_rank = self.getMetrics(link)
            self.d.append((title, link, pubDate, description, source, query, alexa_rank))
            # print(self.d)
        # Add delay between calls
        time.sleep(2)

    def scrape(self):
        # Looping the different combination of queries and places
        if len(self.locations) > 0:
            # Looping queries and places 
            for a in self.queries:
                for b in self.locations:
                    query = ''.join(map(str, a))
                    # URL encode the query and add quotes around it
                    encoded_query = '"' + urllib.parse.quote_plus(query) + '"'
                    place = urllib.parse.quote_plus(''.join(map(str, b)).upper() + ":" + ''.join(map(str, b)).lower()) 
                    # Compose the URL
                    url = self.base_url + encoded_query + "&hl=" + self.language + "&ceid=" + place 
                    # print("Reading now: ", url)
                    # Read the Feed
                    self.readFeed(url, query)
        else: 
            # Just use the query(ies)
            for a in self.queries:   
                query = ''.join(map(str, a))
                # URL encode the query and add quotes around it
                encoded_query = '"' + urllib.parse.quote_plus(query) + '"'        
                # Compose the URL    
                url = self.base_url + encoded_query
                # print("Reading now: ",url)
                # Read the Feed
                self.readFeed(url, query)

        # Set the file name
        cleanQuery = re.sub('\W+','', query)
        file_name = cleanQuery + ".csv"

        df = pd.DataFrame(self.d, columns=('Title', 'Link', 'pubDate', 'Description','Source', 'Query', 'Alexa Rank'))

                                           # Remove all rows with the same link - you might want to comment this when using different keywords
        df.drop_duplicates(subset ="Link", keep = False, inplace = True)
        return df

        # Store data to CSV
        # df.to_csv(file_name, encoding='utf-8', index=False)
        # print(len(df), "Articles saved on ", file_name)


@app.get("/articles", response_model=List[Article])
async def get_articles(queries: Optional[List[str]] = None, locations: Optional[List[str]] = None):
    if queries is None:
        queries = ['Singapore', 'Malaysia']
    if locations is None:
        locations = ['Singapore']
    language = 'en'

    scraper = NewsScraper(queries, language, locations)
    df = scraper.scrape()

    articles = []

    for _, row in df.iterrows():
        article = {
            'title': row['Title'],
            'link': row['Link'],
            'pub_date': row['pubDate'],
            'description': row['Description'],
            'source': row['Source'],
            'query': row['Query'],
            'alexa_rank': row['Alexa Rank']
        }
        articles.append(article)

    return articles

@app.get("/stories", response_model=List[str])
async def get_stories(queries: Optional[List[str]] = None, locations: Optional[List[str]] = None):
    if queries is None:
        queries = ['Singapore', 'Malaysia']
    if locations is None:
        locations = ['Singapore']

    language = 'en'

    scraper = NewsScraper(queries, language, locations)
    df = scraper.scrape()

    articles = []

    for _, row in df.iterrows():
        article = {
            'title': row['Title'],
            'link': row['Link'],
            'pub_date': row['pubDate'],
            'description': row['Description'],
            'source': row['Source'],
            'query': row['Query'],
            'alexa_rank': row['Alexa Rank']
        }
        articles.append(article)

    print(articles)


    # 1. Rank the DataFrame by the 'Link' column
    df = df.sort_values(by=['Link'])

    # 2. Group similar news descriptions, create a new column concatenating those descriptions, and summarize the description items.
    df['concatenated_description'] = df.groupby('Source')['Description'].transform(lambda x: ' '.join(x))
    df = df.drop_duplicates(subset='Source').reset_index(drop=True)

    # 3. Create a story out of the description and limit the DataFrame to only 5 rows.
    df = df.head(7)

    # Get the stories
    story_prompts = ["summarize the following news descriptions: in 15 words " + desc for desc in df['concatenated_description']]
    stories = await asyncio.gather(*(generate_text(prompt) for prompt in story_prompts))

    return stories

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
