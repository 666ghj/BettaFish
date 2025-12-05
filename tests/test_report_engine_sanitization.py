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

    def test_engine_quote_validation(self):
        validator = IRValidator()
        chapter = {
            "chapterId": "S1",
            "title": "Engine 引用校验",
            "anchor": "section-1",
            "order": 1,
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "insight",
                    "title": "Insight Agent",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "来自 Insight Engine 的观点"}],
                        }
                    ],
                }
            ],
        }
        valid, errors = validator.validate_chapter(chapter)
        self.assertTrue(valid, errors)
        self.assertFalse(errors)

    def test_engine_quote_rejects_disallowed_marks_and_blocks(self):
        validator = IRValidator()
        chapter = {
            "chapterId": "S1",
            "title": "Engine 引用校验",
            "anchor": "section-1",
            "order": 1,
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "media",
                    "title": "Media Agent",
                    "blocks": [
                        {"type": "math", "latex": "x=y"},
                        {
                            "type": "paragraph",
                            "inlines": [
                                {"text": "test", "marks": [{"type": "color"}]}
                            ],
                        },
                    ],
                }
            ],
        }
        valid, errors = validator.validate_chapter(chapter)
        self.assertFalse(valid)
        self.assertTrue(any("仅允许 paragraph" in err for err in errors))
        self.assertTrue(any("仅允许 bold/italic" in err for err in errors))

    def test_engine_quote_sanitization_strips_disallowed(self):
        chapter = {
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "query",
                    "blocks": [
                        {"type": "list", "items": [["非法"]]},
                        {
                            "type": "paragraph",
                            "inlines": [
                                {
                                    "text": "abc",
                                    "marks": [{"type": "bold"}, {"type": "highlight"}],
                                }
                            ],
                        },
                    ],
                }
            ]
        }
        node = self.node
        node._sanitize_chapter_blocks(chapter)
        eq_block = chapter["blocks"][0]
        self.assertEqual(eq_block["type"], "engineQuote")
        self.assertEqual(eq_block.get("title"), "Query Agent")
        inner_blocks = eq_block.get("blocks")
        self.assertTrue(all(b.get("type") == "paragraph" for b in inner_blocks))
        marks = inner_blocks[0]["inlines"][0].get("marks")
        self.assertEqual(marks, [])
        marks2 = inner_blocks[1]["inlines"][0].get("marks")
        self.assertEqual(marks2, [{"type": "bold"}])

    def test_engine_quote_title_must_match_engine(self):
        validator = IRValidator()
        chapter = {
            "chapterId": "S1",
            "title": "Engine 引用校验",
            "anchor": "section-1",
            "order": 1,
            "blocks": [
                {
                    "type": "engineQuote",
                    "engine": "query",
                    "title": "Media Agent",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "错误标题"}],
                        }
                    ],
                }
            ],
        }
        valid, errors = validator.validate_chapter(chapter)
        self.assertFalse(valid)
        self.assertTrue(any("title 必须与engine一致" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
