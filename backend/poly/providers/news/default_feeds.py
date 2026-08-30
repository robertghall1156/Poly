"""Curated default feeds across perspectives + primary government sources.

Everything here is a public RSS/Atom feed. Users can add/remove feeds in Settings → News.
`source_type` and `ideology` are recorded on the Source row (ideology only where widely
characterised and relevant to reading the source, e.g. think tanks). Reliability notes are
deliberately brief and factual.
"""

DEFAULT_FEEDS: list[dict] = [
    # ---- wire services & national ----
    {"name": "AP Top News", "url": "https://rsshub.app/apnews/topics/apf-topnews", "category": "national", "source": ("Associated Press", "apnews.com", "wire", None, "Wire service; primary reporting.")},
    {"name": "Reuters — Politics (Google News)", "url": "https://news.google.com/rss/search?q=site:reuters.com+politics&hl=en-US&gl=US&ceid=US:en", "category": "national", "source": ("Reuters", "reuters.com", "wire", None, "Wire service; primary reporting.")},
    {"name": "NPR Politics", "url": "https://feeds.npr.org/1014/rss.xml", "category": "national", "source": ("NPR", "npr.org", "broadcast", None, "Public broadcaster.")},
    {"name": "PBS NewsHour Politics", "url": "https://www.pbs.org/newshour/feeds/rss/politics", "category": "national", "source": ("PBS NewsHour", "pbs.org", "broadcast", None, "Public broadcaster.")},
    {"name": "The Hill", "url": "https://thehill.com/feed/", "category": "national", "source": ("The Hill", "thehill.com", "newspaper", None, "Congress-focused outlet.")},
    {"name": "Politico", "url": "https://rss.politico.com/politics-news.xml", "category": "national", "source": ("Politico", "politico.com", "newspaper", None, "Political news; heavy on process.")},
    {"name": "Axios", "url": "https://api.axios.com/feed/", "category": "national", "source": ("Axios", "axios.com", "newspaper", None, "Short-form; often sourced from insiders.")},
    {"name": "NYT Politics", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml", "category": "national", "source": ("The New York Times", "nytimes.com", "newspaper", None, "National paper; separate opinion section.")},
    {"name": "Washington Post Politics", "url": "https://feeds.washingtonpost.com/rss/politics", "category": "national", "source": ("The Washington Post", "washingtonpost.com", "newspaper", None, "National paper; separate opinion section.")},
    {"name": "WSJ — Politics (Google News)", "url": "https://news.google.com/rss/search?q=site:wsj.com+politics&hl=en-US&gl=US&ceid=US:en", "category": "national", "source": ("The Wall Street Journal", "wsj.com", "newspaper", None, "National paper; editorial page is distinct from news.")},
    {"name": "Fox News Politics", "url": "https://moxie.foxnews.com/google-publisher/politics.xml", "category": "national", "source": ("Fox News", "foxnews.com", "broadcast", "right-leaning", "Distinguish news reporting from opinion programming.")},
    {"name": "CNN Politics", "url": "http://rss.cnn.com/rss/cnn_allpolitics.rss", "category": "national", "source": ("CNN", "cnn.com", "broadcast", "left-leaning", "Distinguish news reporting from opinion programming.")},
    {"name": "Washington Examiner", "url": "https://www.washingtonexaminer.com/feed", "category": "national", "source": ("Washington Examiner", "washingtonexaminer.com", "magazine", "right-leaning", "Conservative outlet.")},
    {"name": "The Atlantic — Politics", "url": "https://www.theatlantic.com/feed/channel/politics/", "category": "analysis", "source": ("The Atlantic", "theatlantic.com", "magazine", "left-leaning", "Long-form analysis and opinion.")},
    {"name": "National Review", "url": "https://www.nationalreview.com/feed/", "category": "analysis", "source": ("National Review", "nationalreview.com", "magazine", "right-leaning", "Conservative opinion magazine.")},
    {"name": "Reason", "url": "https://reason.com/latest/feed/", "category": "analysis", "source": ("Reason", "reason.com", "magazine", "libertarian", "Libertarian magazine.")},
    # ---- business / economy ----
    {"name": "CNBC Economy", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html", "category": "economy", "source": ("CNBC", "cnbc.com", "broadcast", None, "Business news.")},
    {"name": "Bloomberg — Economics (Google News)", "url": "https://news.google.com/rss/search?q=site:bloomberg.com+economy&hl=en-US&gl=US&ceid=US:en", "category": "economy", "source": ("Bloomberg", "bloomberg.com", "newspaper", None, "Business/markets news.")},
    # ---- government primary sources ----
    {"name": "Federal Register — Public Inspection", "url": "https://www.federalregister.gov/api/v1/public-inspection-documents.rss", "category": "government", "source": ("Federal Register", "federalregister.gov", "government", None, "Primary source.")},
    {"name": "White House — Briefings", "url": "https://www.whitehouse.gov/feed/", "category": "government", "source": ("The White House", "whitehouse.gov", "government", None, "Primary source; executive branch messaging.")},
    {"name": "Congress.gov — Bills Presented to President", "url": "https://www.congress.gov/rss/presented-to-president.xml", "category": "government", "source": ("Congress.gov", "congress.gov", "government", None, "Primary source.")},
    {"name": "Congress.gov — Most Viewed Bills", "url": "https://www.congress.gov/rss/most-viewed-bills.xml", "category": "government", "source": ("Congress.gov", "congress.gov", "government", None, "Primary source.")},
    {"name": "Supreme Court — Opinions (Google News)", "url": "https://news.google.com/rss/search?q=%22Supreme+Court%22+opinion+ruling&hl=en-US&gl=US&ceid=US:en", "category": "courts", "source": None},
    {"name": "CBO", "url": "https://www.cbo.gov/publications/all/rss.xml", "category": "government", "source": ("Congressional Budget Office", "cbo.gov", "government", None, "Nonpartisan primary analysis.")},
    {"name": "GAO Reports", "url": "https://www.gao.gov/rss/reports.xml", "category": "government", "source": ("Government Accountability Office", "gao.gov", "government", None, "Nonpartisan primary audits.")},
    {"name": "BLS — Latest Releases", "url": "https://www.bls.gov/feed/bls_latest.rss", "category": "economy", "source": ("Bureau of Labor Statistics", "bls.gov", "government", None, "Primary statistics.")},
    {"name": "BEA News", "url": "https://apps.bea.gov/rss/rss.xml", "category": "economy", "source": ("Bureau of Economic Analysis", "bea.gov", "government", None, "Primary statistics.")},
    {"name": "Federal Reserve — Press Releases", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "category": "economy", "source": ("Federal Reserve", "federalreserve.gov", "government", None, "Primary source.")},
    {"name": "SEC Press Releases", "url": "https://www.sec.gov/news/pressreleases.rss", "category": "corporate", "source": ("SEC", "sec.gov", "government", None, "Primary source.")},
    {"name": "Census — Newsroom", "url": "https://www.census.gov/newsroom/press-releases.rss", "category": "economy", "source": ("U.S. Census Bureau", "census.gov", "government", None, "Primary statistics.")},
    # ---- think tanks across perspectives ----
    {"name": "Brookings", "url": "https://www.brookings.edu/feed/", "category": "think_tank", "source": ("Brookings Institution", "brookings.edu", "think_tank", "center-left", "Policy research.")},
    {"name": "American Enterprise Institute", "url": "https://www.aei.org/feed/", "category": "think_tank", "source": ("AEI", "aei.org", "think_tank", "center-right", "Policy research.")},
    {"name": "Cato Institute", "url": "https://www.cato.org/rss/recent-op-eds", "category": "think_tank", "source": ("Cato Institute", "cato.org", "think_tank", "libertarian", "Policy research.")},
    {"name": "Urban Institute", "url": "https://www.urban.org/rss.xml", "category": "think_tank", "source": ("Urban Institute", "urban.org", "think_tank", "center-left", "Policy research.")},
    {"name": "Tax Policy Center", "url": "https://www.taxpolicycenter.org/rss.xml", "category": "think_tank", "source": ("Tax Policy Center", "taxpolicycenter.org", "think_tank", "nonpartisan", "Tax analysis (Urban-Brookings).")},
    {"name": "Tax Foundation", "url": "https://taxfoundation.org/feed/", "category": "think_tank", "source": ("Tax Foundation", "taxfoundation.org", "think_tank", "center-right", "Tax analysis.")},
    {"name": "Economic Policy Institute", "url": "https://www.epi.org/feed/", "category": "think_tank", "source": ("Economic Policy Institute", "epi.org", "think_tank", "left-leaning", "Labor-aligned research.")},
    {"name": "Manhattan Institute", "url": "https://manhattan.institute/feed", "category": "think_tank", "source": ("Manhattan Institute", "manhattan.institute", "think_tank", "center-right", "Policy research.")},
    {"name": "Niskanen Center", "url": "https://www.niskanencenter.org/feed/", "category": "think_tank", "source": ("Niskanen Center", "niskanencenter.org", "think_tank", "center", "Policy research.")},
    {"name": "KFF Health Policy", "url": "https://www.kff.org/feed/", "category": "healthcare", "source": ("KFF", "kff.org", "think_tank", "nonpartisan", "Health policy research.")},
    # ---- topic queries via Google News RSS ----
    {"name": "Google News — executive compensation", "url": "https://news.google.com/rss/search?q=%22executive+compensation%22+OR+%22CEO+pay%22&hl=en-US&gl=US&ceid=US:en", "category": "corporate", "source": None},
    {"name": "Google News — AI and jobs", "url": "https://news.google.com/rss/search?q=AI+jobs+automation+layoffs&hl=en-US&gl=US&ceid=US:en", "category": "ai", "source": None},
    {"name": "Google News — campaign finance", "url": "https://news.google.com/rss/search?q=%22campaign+finance%22+OR+%22super+PAC%22&hl=en-US&gl=US&ceid=US:en", "category": "elections", "source": None},
    {"name": "Google News — immigration reform", "url": "https://news.google.com/rss/search?q=%22immigration+reform%22+OR+%22legal+immigration%22&hl=en-US&gl=US&ceid=US:en", "category": "immigration", "source": None},
    {"name": "Google News — Pentagon procurement", "url": "https://news.google.com/rss/search?q=Pentagon+procurement+OR+%22defense+budget%22&hl=en-US&gl=US&ceid=US:en", "category": "defense", "source": None},
    {"name": "Google News — veterans", "url": "https://news.google.com/rss/search?q=veterans+VA+benefits&hl=en-US&gl=US&ceid=US:en", "category": "veterans", "source": None},
]
