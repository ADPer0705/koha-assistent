"""Unit tests for KOHA response parsing (no network)."""

from __future__ import annotations

from app.koha import KohaClient

RSS_SAMPLE = """<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0"
     xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>NFSU Search for 'kw,wrdl: forensic'</title>
    <opensearch:totalResults>572</opensearch:totalResults>
    <item>
      <title> Forensic science under siege : the challenges / </title>
      <dc:identifier>ISBN:9780123708618</dc:identifier>
      <link>https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=1690</link>
      <description><![CDATA[<img src="x.jpg" />]]></description>
      <guid>https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=1690</guid>
    </item>
    <item>
      <title>The Basics of Digital Forensics /</title>
      <dc:identifier>ISBN:9780128018927</dc:identifier>
      <link>https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=2281</link>
      <guid>https://catalog.nfsu.ac.in/cgi-bin/koha/opac-detail.pl?biblionumber=2281</guid>
    </item>
  </channel>
</rss>
"""

MARC_SAMPLE = {
    "leader": "00464nam a2200169Ia 4500",
    "fields": [
        {"020": {"ind1": " ", "ind2": " ", "subfields": [{"a": "9780335212361"}]}},
        {"100": {"ind1": " ", "ind2": " ", "subfields": [{"a": "Paul, Bennett"}]}},
        {
            "245": {
                "ind1": " ",
                "ind2": "0",
                "subfields": [
                    {"a": "Abnormal and Clinical Psychology /"},
                    {"c": "Bennett Paul"},
                ],
            }
        },
        {
            "260": {
                "ind1": " ",
                "ind2": " ",
                "subfields": [{"a": "London: "}, {"b": "Open University Press, "}, {"c": "2003."}],
            }
        },
        {"650": {"ind1": " ", "ind2": " ", "subfields": [{"a": "Clinical psychology"}]}},
    ],
}


def test_parse_rss_returns_hits_and_total():
    hits, total = KohaClient._parse_rss(RSS_SAMPLE, limit=10)
    assert total == 572
    assert len(hits) == 2
    assert hits[0].biblio_id == 1690
    assert "Forensic science" in hits[0].title
    assert hits[0].isbn == "9780123708618"


def test_parse_rss_respects_limit():
    hits, _ = KohaClient._parse_rss(RSS_SAMPLE, limit=1)
    assert len(hits) == 1


def test_parse_marc_extracts_metadata():
    details = KohaClient._parse_marc(1, MARC_SAMPLE)
    assert details.title.startswith("Abnormal and Clinical Psychology")
    assert details.author == "Paul, Bennett"
    assert details.publisher == "Open University Press"
    assert details.year == "2003"
    assert details.isbn == "9780335212361"
    assert details.subjects == ["Clinical psychology"]
    assert "biblionumber=1" in details.url


def test_opac_search_url_encodes_terms():
    client = KohaClient("https://catalog.nfsu.ac.in")
    url = client.opac_search_url("forensic DNA", "kw")
    assert "idx=kw" in url
    assert "forensic%20DNA" in url


def test_supported_indexes():
    from app.koha import VALID_INDEXES

    assert {"kw", "ti", "au", "su", "isbn"} <= VALID_INDEXES
