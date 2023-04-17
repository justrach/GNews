import feedparser
import time
import sys
import pandas as pd
import re
import urllib
import urllib.request as ur
import argparse
import bs4

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




queries = ['Apple', 'Microsoft']
locations = ['United States']
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
df
