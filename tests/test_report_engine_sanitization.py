import unittest

from ReportEngine.ir import IRValidator
from ReportEngine.nodes.chapter_generation_node import ChapterGenerationNode


class ChapterSanitizationTestCase(unittest.TestCase):
    """Lightweight regression tests for the chapter sanitization helpers."""

    def setUp(self):
        self.node = ChapterGenerationNode(llm_client=None, validator=IRValidator(), storage=None)

    def test_table_cell_empty_blocks_repaired(self):
        chapter = {
            "blocks": [
                {
                    "type": "table",
                    "rows": [
                        {
                            "cells": [
                                {"blocks": []},
                                {"text": "同比变化", "blocks": None},
                            ]
                        }
                    ],
                }
            ]
        }
        self.node._sanitize_chapter_blocks(chapter)
        table_block = chapter["blocks"][0]
        cells = table_block["rows"][0]["cells"]
        self.assertEqual(len(cells), 2)
        for cell in cells:
            blocks = cell.get("blocks")
            self.assertIsInstance(blocks, list)
            self.assertGreater(len(blocks), 0)
            for block in blocks:
                self.assertEqual(block.get("type"), "paragraph")

    def test_table_rows_scalar_values_expanded(self):
        chapter = {"blocks": [{"type": "table", "rows": ["全国趋势"]}]}
        self.node._sanitize_chapter_blocks(chapter)
        table_block = chapter["blocks"][0]
        self.assertEqual(len(table_block["rows"]), 1)
        row = table_block["rows"][0]
        self.assertIn("cells", row)
        self.assertEqual(len(row["cells"]), 1)
        cell = row["cells"][0]
        self.assertIsInstance(cell.get("blocks"), list)
        self.assertEqual(
            cell["blocks"][0]["inlines"][0]["text"],
            "全国趋势",
        )


if __name__ == "__main__":
    unittest.main()
