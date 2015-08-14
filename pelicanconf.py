#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = 'Tobias Macey'
SITENAME = 'The Renaissance Dev'
SITEURL = ''

PATH = 'content'

TIMEZONE = 'America/New_York'

DEFAULT_LANG = 'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Blogroll
LINKS = (
    ('Boundless Notions', 'http://www.boundlessnotions.com'),
    ('Podcast.__init__', 'http://www.podcastinit.com'),
)

# Social widget
SOCIAL = (('LinkedIn', 'http://linkedin.com/in/tmacey'),
          ('Twitter', 'https://twitter.com/TobiasMacey'),
          ('GitHub', 'https://github.com/blarghmatey'),
          ('BitBucket', 'https://bitbucket.org/blarghmatey'))

DEFAULT_PAGINATION = 10
DEFAULT_CATEGORY = 'General'

TYPOGRIFY = True
THEME = 'themes/elegant'
# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True
PLUGIN_PATHS = ['plugins']
PLUGINS = ['better_code_samples', 'sitemap', 'share_post', 'extract_toc',
           'tipue_search']
MD_EXTENSIONS=['codehilite(css_class=highlight)', 'extra', 'headerid', 'toc']
DIRECT_TEMPLATES = (('index', 'tags', 'categories', 'archives', 'search',
                     '404'))
TWITTER_USERNAME="TobiasMacey"
TAG_SAVE_AS=''
CATEGORY_SAVE_AS=''
AUTHOR_SAVE_AS=''
COMMENTS_INTRO=('All corrections, suggestions and feedback are welcome.')
