# -*- coding: utf-8 -*-
"""
2024-09-21 ebb: This is adapted from the hypermail.py scraper to pull listserv data from the public TEI-L mailing list archive at
https://lists.psu.edu/cgi-bin/wa?A0=TEI-L

This retrieves messages from January 1, 1990 to December 31, 1995:
https://lists.psu.edu/cgi-bin/wa?A1=199001-199512&L=TEI-L

On the page, the HTML structure showing the available messages is a table:

<table class="width-100 nopadding border" id="TEI-L-a1-table">
...
<tr>
<td class="normalgroup row-l" scope="row"><div class="archive forcewrap"> <span onmouseover="showDesc('Several astute correspondents have justly observed the irony which&amp;lt;br&amp;gt;inheres in the current plan of making the TEI Guidelines for&amp;lt;br&amp;gt;*electronic* texts available only in *hardcopy* form. We (I speak for&amp;lt;br&amp;gt;my colleagues as well as myself, I know) are acutely aware of the irony&amp;lt;br&amp;gt;ourselves, and plan to rectify it as soon as possible. We are&amp;lt;br&amp;gt;determined to do this, however, by making the TEI guidelines available&amp;lt;br&amp;gt;in the form prescribed *by* the TEI guidelines. The guidelines are not&amp;lt;br&amp;gt;now, however, in the format they themselves prescribe, for the simple&amp;lt;br&amp;gt;reason that they were not completed until they were [...]','electronic copies of the TEI guidelines','Wed, 8 Aug 90 12:36:34 CDT')" onmouseout="hideDesc()"><a href="/cgi-bin/wa?A2=TEI-L;450aa1ac.9008&amp;S=">electronic copies of the TEI guidelines</a></span></div></td>
<td class="normalgroup row-l"><div class="archive forcewrap">Michael Sperberg-McQueen 312 996-2477 -2981 &amp;lt;U35395@UICVM.BITNET&amp;gt;</div></td>
<td class="normalgroup nowrap row-l"><div class="archive forcewrap">Wed, 8 Aug 90 12:36:34 CDT</div></td>
<td class="normalgroup right row-l"><a href="/cgi-bin/wa?MD=TEI-L&amp;i=9008&amp;I=1726938160&amp;s=1290&amp;l=35&amp;X=O544A51E82796CD5F9E&amp;Y=eeb4%40psu.edu&amp;URL=A1%3D199001-199412%26L%3DTEI-L%26X%3DO544A51E82796CD5F9E%26Y%3Deeb4%2540psu.edu&amp;M_S=electronic+copies+of+the+TEI+guidelines&amp;M_F=Michael+Sperberg-McQueen+312+996-2477+-2981+%26lt%3BU35395%40UICVM.BITNET%26gt%3B&amp;M_D=Wed%2C+8+Aug+90+12%3A36%3A34+CDT&amp;M_Z=35+Lines&amp;A1DATE=&amp;A2URL=https%3A%2F%2Flists.psu.edu%2Fcgi-bin%2Fwa%3FA2%3Dindex%26L%3DTEI-L%26O%3DD%26X%3DO544A51E82796CD5F9E%26Y%3Deeb4%2540psu.edu%26P%3D27190"><img src="/archives/images/default_archive_delete_22x22.png" alt="Delete Message" title="Delete Message" /></a></td>
</tr>

...
</table>

Each mail message is accessible by this XPath: //table[@id="TEI-L-a1-table"]//tr/td[1]//a/@href

The @href values are formatted like this: /cgi-bin/wa?A2=TEI-L;9e3ba26.9001&amp;S=

concat the TEI listserv archive to the front of the @href value
https://lists.psu.edu

https://lists.psu.edu/cgi-bin/wa?A2=TEI-L;9e3ba26.9001&amp;S=

"""

import re

import scrapy
from dask.dataframe.methods import values
from scrapy.loader import ItemLoader
from mailingListScraper.items import Email
from mailingListScraper.spiders.ArchiveSpider import ArchiveSpider


class TEILSpider(ArchiveSpider):
    name = "TEI-L"
    allowed_domains = ["lists.psu.edu"]

    # Email Lists available from Hypermail archive:
    mailing_lists = {
        'tei-l': 'https://lists.psu.edu/cgi-bin/wa?A1=199001-199512&L=TEI-L',
    }
    default_list = 'tei-l'

    def parse(self, response):
        """
        Extract all of the messages lists (grouped by date).

        @url https://lists.psu.edu/cgi-bin/wa?A0=TEI-L
        @returns requests 1002
        """

        msglist_urls = response.xpath('//table[@id="TEI-L-a1-table"]//tr/td[1]//a/@href').extract()
        msglist_urls = ['https://lists.psu.edu/' + u for u in msglist_urls]

        # if any(self.years):
        #     urls = []
        #
        #     for year in self.years:
        #         pattern = response.url + year[2:]
        #         urls.extend([u for u in msglist_urls if pattern in u])
        #
        #     msglist_urls = urls

        for url in msglist_urls:
            yield scrapy.Request(url, callback=self.parse_msglist)

    def parse_msglist(self, response):
        """
        Extract all relative URLs to the individual messages.

        @url http://lkml.iu.edu/hypermail/linux/kernel/9506/index.html
        @returns requests 199
        """

        msg_urls = response.xpath('//table[@id="TEI-L-a1-table"]//tr/td[1]//a/@href').extract()
        # reg_url = re.search(r'^(.*)/index\.html', response.url)
        base_url = 'https://lists.psu.edu'

        # TODO: refactor here
        for rel_url in msg_urls:
            msg_url = base_url + '/' + rel_url
            yield scrapy.Request(msg_url, callback=self.parse_item)
            print('help')

    def parse_item(self, response):
        """
        Extract fields from the individual email page and load them into the
        item.

        @url http://lkml.iu.edu/hypermail/linux/kernel/0111.3/0036.html
        @returns items 1 1
        @scrapes senderName senderEmail timeSent timeReceived subject body
        @scrapes replyto url
        """

        load = ItemLoader(item=Email(), selector=response)

        # Take care of easy fields first
        load.add_value('url', response.url)

        # pattern_replyto = '//ul[1]/li[contains((b|strong), "In reply to:")]'
        # pattern_replyto += '/a/@href'
        # link = response.xpath(pattern_replyto).extract()
        # link = [''] if not link else link

        # load.add_value('replyto', link[0])

        specific_fields = {
            'subject': 'Subject:',
            'senderName': 'From:',
            'timestampReceived': 'Date:',
            'body': 'pre',
        }

        specific_fields = self.parse_system(response, specific_fields)


        # Load all the values from these specific fields
        for key, val in specific_fields.items():
            load.add_value(key, val)
            print(key)

        return load.load_item()



    def parse_system(self, response, fields):
        """
        Populates the fields dictionary for responses that were generated
        by the old archive system (before 2003).
        """
        print(fields)

        selectors = {
            'subject': 'Subject:',
            'senderName': 'From:',
            'timestampReceived': 'Date:',
            'body': 'pre',
        }

        for item, sel in selectors.items():
            # xpath = "(//b[.='" + sel + "']/following::div[1]/text() | //*[name()='" + sel + "']/string())"
            xpath = "//b[.='" + sel + "']"
            content = response.xpath(xpath).extract()
            # value = re.search('"(.*)"', content[0]).group(1)

            fields[item] = content
            print('whaaa')
            print('VALUE' + content)

        return fields
