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
)

# Social widget
SOCIAL = (('LinkedIn', 'http://linkedin.com/in/tmacey'),
          ('Twitter', 'https://twitter.com/TobiasMacey'),
          ('GitHub', 'https://github.com/blarghmatey'),
          ('BitBucket', 'https://bitbucket.org/blarghmatey'))

DEFAULT_PAGINATION = 10
DEFAULT_CATEGORY = 'General'

TYPOGRIFY = True
THEME = 'themes/blueidea'
# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True
