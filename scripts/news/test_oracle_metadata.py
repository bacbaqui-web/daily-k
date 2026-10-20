import unittest
from oracle_runner import clean_publication_metadata, PUBLISHER_FIELDS

class PublicationMetadataTests(unittest.TestCase):
    def test_strip_only_publisher_fields(self):
        brief = {key: "AI supplied value" for key in PUBLISHER_FIELDS}
        brief.update(id="2026-10-20-pm", generatedAt="original",
                     stories=[{"publishedAt":"article time","sources":[{"publishedAt":"source time"}]}])
        clean_publication_metadata(brief)
        self.assertTrue(all(key not in brief for key in PUBLISHER_FIELDS))
        self.assertEqual(brief["generatedAt"], "original")
        self.assertEqual(brief["stories"][0]["publishedAt"], "article time")
        self.assertEqual(brief["stories"][0]["sources"][0]["publishedAt"], "source time")
        self.assertEqual(clean_publication_metadata(brief), brief)

if __name__ == "__main__":
    unittest.main()
