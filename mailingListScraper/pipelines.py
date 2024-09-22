# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring,too-few-public-methods,unused-argument
# pylint: disable=no-self-use
"""
Pipelines that handle the scraped data, format it and save it.
"""

import re
import logging
import os
from datetime import datetime
from dateutil.parser import parse as dateParser
from dateutil import tz

from scrapy import signals
from scrapy.exporters import CsvItemExporter, XmlItemExporter

LOGGER = logging.getLogger('pipelines')


class GenerateId(object):
    """
    Generate a unique ID for the email.

    Each email should have its own unique ID. This pipeline generates it with
    the received timestamp, because I make the assumption that few emails will
    share the same timestamp down to the second. For those who do, the (n+1)th
    processed item gets n zeros added to their timestamp.
    """

    def __init__(self):
        self.existing_ids = set()

    def process_item(self, item, spider):
        time_format = "%Y-%m-%d %H:%M:%S%z"
        timestamp = datetime.strptime(item['timestampReceived'], time_format)

        id_format = "%Y%m%d%H%M%S"
        email_id = int(timestamp.strftime(id_format))

        # If two emails were received at the same time, multiply by 10
        # (i.e. add a 0 at the end of the ID)
        email_id = email_id*10 if email_id in self.existing_ids else email_id

        self.existing_ids.add(email_id)

        item['emailId'] = email_id

        return item


class CleanReplyto(object):
    """
    Clean the "replyto" field.

    1. Return NA if not in reply to another email
    2. Reconstruct the entire URL if we only get a relative URL
    """

    def process_item(self, item, spider):
        if item['replyto'] == '':
            item['replyto'] = 'NA'
            return item

        if spider.name == 'hypermail':
            base_url = re.search(r'^(.*)/\d{4,6}\.html', item['url']).group(1)
            item['replyto'] = base_url + '/' + item['replyto']

        return item


class ParseTimeFields(object):
    """
    Create well formated timestamps with existing time fields.

    1. Return NA when appropriate (time missing or unreadable)
    2. Use dateutil to parse the field and format it
    """

    def process_item(self, item, spider):
        times = {
            'timestampSent': 'timeSent',
        }

        time_format = "%Y-%m-%d %H:%M:%S%z"

        # Define a default time zone according to the email server setting
        if spider.name == 'hypermail':
            def_tz = tz.tzoffset('EST', -18000)
        elif spider.name == 'marc':
            def_tz = tz.tzoffset('EDT', -14400)

        for key, val in times.items():
            if item[val] == "":
                item[val] = "NA"
                item[key] = "NA"
                continue

            try:
                parsed_time = dateParser(item[val])
            except ValueError:
                try:
                    # "... HH:MM:SS +0200"
                    pattern = r'(.* \d{2}:\d{2}:\d{2}(\s?[+,-]\d{4})?)'
                    simpler = re.search(pattern, item[val])
                    parsed_time = dateParser(simpler.group(1))
                except AttributeError:
                    message = '<' + item['url'] + '> '
                    message += 'ParseTimeFields could not parse ' + val + ', '
                    message += key + ' will be NA.'
                    LOGGER.warning(message)
                    item[key] = "NA"
                    continue

            if parsed_time.tzinfo is None:
                parsed_time = parsed_time.replace(tzinfo=def_tz)

            item[key] = parsed_time.strftime(time_format)

        return item

class CleanSenderEmail(object):
    """
    Clean the senderEmail field.
    """

    def process_item(self, item, spider):
        if spider.name == 'marc' and 'senderEmail' in item:
            email = item['senderEmail']
            email = email.lower()
            email = email.replace(' () ', '@')
            email = email.replace(' ! ', '.')
            item['senderEmail'] = email

        return item

class GetMailingList(object):
    """
    Get the mailing list.
    """

    def process_item(self, item, spider):
        for mlist, url in spider.mailing_lists.items():
            if url in item['url']:
                item['mailingList'] = mlist

        return item


class XmlExport(object):
    """
    Export email body to a separate file.
    """

    def __init__(self):
        self.fields_to_export = ['mailingList', 'senderName', 'timestampReceived','subject', 'body']
        self.file_base = ''
        self.exporters = {}

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        crawler.signals.connect(pipeline.spider_opened, signals.spider_opened)
        crawler.signals.connect(pipeline.spider_closed, signals.spider_closed)
        return pipeline

    def spider_opened(self, spider):
        """
        When spider opens, set up fields and base of filename
        """

        if not spider.get_body:
            return

        if not os.path.exists('data'):
            os.makedirs('data')

        if len(spider.scraping_lists) == 1:
            self.file_base = 'data/{}'.format(spider.scraping_lists[0])
            self.fields_to_export.remove('mailingList')
        else:
            self.file_base = 'data/{}'.format(spider.name)

        self.fields_to_export = [f for f in self.fields_to_export if f not in spider.drop_fields]

    def spider_closed(self, spider):
        """
        When spider closes, close everything gently
        """

        if not spider.get_body:
            return

        for year_item in self.exporters.values():
            year_item['exporter'].finish_exporting()
            year_item['file'].close()

    def process_item(self, item, spider):
        """
        Process each item to export them according to their year.
        """
        if not spider.get_body:
            return item

        # Get the year
        # Mon, 8 Jan 90 16:08:22 CST
        # time_format = "%Y-%m-%d %H:%M:%S%z"
        time_format = "%a, %d %b %y %H:%M:%S %Z"
        timestamp = datetime.strptime(item['timestampReceived'], time_format)
        year = str(timestamp.year)
        filename = self.file_base + year + 'Bodies.xml'

        if year in self.exporters:
            # If we already have an exporter for this year, select it
            exporter = self.exporters[year]['exporter']
        else:
            # If we encounter this year for the first time, then:
            # Open a new file
            dest_file = open(filename, 'wb')

            # Store file and create exporter in dictionary
            self.exporters[year] = {
                'file': dest_file,
                'exporter': XmlItemExporter(dest_file)
            }

            # Initialize the exporter
            exporter = self.exporters[year]['exporter']
            exporter.root_element = 'emails'
            exporter.item_element = 'email'
            exporter.fields_to_export = self.fields_to_export
            exporter.start_exporting()

        # Now we can export the item for real
        exporter.export_item(item)
        return item

class CsvExport(object):
    """
    Export items to a csv file.
    """

    def __init__(self):
        self.files = {}
        self.exporter = {}

    @classmethod
    def from_crawler(cls, crawler):
        pipeline = cls()
        crawler.signals.connect(pipeline.spider_opened, signals.spider_opened)
        crawler.signals.connect(pipeline.spider_closed, signals.spider_closed)
        return pipeline

    def spider_opened(self, spider):
        fields_to_export = ['mailingList', 'senderName', 'timestampReceived','subject', 'body']

        fields_to_export = [f for f in fields_to_export if f not in spider.drop_fields]

        if not os.path.exists('data'):
            os.makedirs('data')

        if len(spider.scraping_lists) == 1:
            dest_file_path = 'data/{}ByEmail.csv'.format(spider.scraping_lists[0])
            fields_to_export.remove('mailingList')
        else:
            dest_file_path = 'data/{}ByEmail.csv'.format(spider.name)

        dest_file = open(dest_file_path, 'wb')

        self.exporter = CsvItemExporter(dest_file)
        self.files[spider] = dest_file
        self.exporter.fields_to_export = fields_to_export

        self.exporter.start_exporting()

    def spider_closed(self, spider):
        self.exporter.finish_exporting()
        dest_file = self.files.pop(spider)
        dest_file.close()

    def process_item(self, item, spider):
        self.exporter.export_item(item)
        return item
