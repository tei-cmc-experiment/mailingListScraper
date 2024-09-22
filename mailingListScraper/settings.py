# -*- coding: utf-8 -*-
"""
Settings for spiders, crawling, etc.
"""

BOT_NAME = 'mailingListScraper'

SPIDER_MODULES = ['mailingListScraper.spiders']
NEWSPIDER_MODULE = 'mailingListScraper.spiders'

LOG_FILE = 'log.txt'
# Comment the following line when doing development.
# For actual scraping, we don't want all the debugging messages.
LOG_LEVEL = 'DEBUG'

# Crawl responsibly by identifying yourself (and your website) on the
# user-agent AND uncomment the following lines before scraping.
# USER_AGENT = 'mailingListScraper '
# USER_AGENT += '(https://github.com/gaalcaras/mailingListScraper)'

# Configure item pipelines and their order
ITEM_PIPELINES = {
    'mailingListScraper.pipelines.ParseTimeFields': 100,
    'mailingListScraper.pipelines.GenerateId': 200,
    'mailingListScraper.pipelines.CleanSenderEmail': 250,
    'mailingListScraper.pipelines.CleanReplyto': 300,
    'mailingListScraper.pipelines.GetMailingList': 400,
    'mailingListScraper.pipelines.XmlExport': 800,
    'mailingListScraper.pipelines.CsvExport': 900,
}
