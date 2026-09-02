import unittest

from paperagent.chunking import chunk_pages, split_text
from paperagent.embeddings import l2_normalize
from paperagent.evaluation import recall_at_k, reciprocal_rank


class CoreTests(unittest.TestCase):
    def test_chunking_keeps_page_metadata(self):
        chunks = chunk_pages([("paper.pdf", 3, "A" * 700)], chunk_size=500, overlap=100)
        self.assertEqual(chunks[0].page, 3)
        self.assertEqual(chunks[0].file_name, "paper.pdf")
        self.assertGreater(len(chunks), 1)

    def test_invalid_chunk_overlap(self):
        with self.assertRaises(ValueError):
            split_text("text", chunk_size=10, overlap=10)

    def test_normalization(self):
        import numpy as np

        output = l2_normalize(np.array([[3.0, 4.0]], dtype="float32"))
        self.assertAlmostEqual(float(np.linalg.norm(output[0])), 1.0)

    def test_retrieval_metrics(self):
        self.assertEqual(recall_at_k(["a", "b"], {"b", "c"}, 2), 0.5)
        self.assertEqual(reciprocal_rank(["a", "b"], {"b"}), 0.5)


if __name__ == "__main__":
    unittest.main()

