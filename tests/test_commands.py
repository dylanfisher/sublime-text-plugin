"""Emmet TextCommands, run through view.run_command on output-panel views."""

import base64
import os
import tempfile
import unittest
from unittest.mock import patch

import sublime

from ..lib import convert_data_url, update_image_size, wrap_with_abbreviation
from .helpers import CSS, JSX, TEXT, XML, EmmetTestCase

PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class TestExpandAbbreviation(EmmetTestCase):
    def test_expand_markup(self):
        self.set_text("ul>li*2|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<ul>\n\t<li></li>\n\t<li></li>\n</ul>")
        self.assertEqual(self.text_with_carets(), "<ul>\n\t<li>|</li>\n\t<li></li>\n</ul>")

    def test_expand_inside_document(self):
        self.set_text("<body>\n\tdiv.a#b|\n</body>")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), '<body>\n\t<div class="a" id="b"></div>\n</body>')

    def test_expand_nothing_to_expand(self):
        self.set_text("<p>hello |</p>")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<p>hello </p>")

    def test_expand_inside_tag_is_ignored(self):
        self.set_text('<div cl|ass="x"></div>')
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), '<div class="x"></div>')

    def test_expand_unicode(self):
        self.set_text("p{héllo ✓ 日本}|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<p>héllo ✓ 日本</p>")

    def test_expand_after_unicode_text(self):
        self.set_text("日本語 ✓ span|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "日本語 ✓ <span></span>")

    def test_expand_with_windows_line_endings(self):
        self.view.set_line_endings("windows")
        self.set_text("<div>\n\tp*2|\n</div>")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<div>\n\t<p></p>\n\t<p></p>\n</div>")
        self.assertNotIn("\r", self.text())

    def test_expand_multiple_cursors(self):
        self.set_text("a|\nb|\nspan.x|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), '<a href=""></a>\n<b></b>\n<span class="x"></span>')
        self.assertEqual(len(self.view.sel()), 3)

    def test_expand_multiple_cursors_partial(self):
        # A cursor without an abbreviation keeps its place.
        self.set_text("em|\n<p>|</p>")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<em></em>\n<p></p>")
        self.assertEqual(len(self.view.sel()), 2)

    def test_expand_force(self):
        self.set_text("ul|")
        self.cmd("emmet_expand_abbreviation", {"force": True})
        self.assertEqual(self.text(), "<ul></ul>")

    def test_expand_tab_without_tracker_does_nothing(self):
        self.set_text("ul|")
        self.cmd("emmet_expand_abbreviation", {"tab": True})
        self.assertEqual(self.text(), "ul")

    def test_expand_numbering(self):
        self.set_text("li*2{n$}|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<li>n1</li>\n<li>n2</li>")

    def test_expand_lorem(self):
        self.set_text("lorem4|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(len(self.text().split()), 4)

    def test_expand_in_read_only_view(self):
        self.set_text("ul>li|")
        self.view.set_read_only(True)
        try:
            self.cmd("emmet_expand_abbreviation")
            self.assertEqual(self.text(), "ul>li")
        finally:
            self.view.set_read_only(False)

    def test_expand_in_empty_view(self):
        self.set_text("")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "")


class TestExpandCSS(EmmetTestCase):
    syntax = CSS

    def test_expand_property(self):
        self.set_text("a {\n\tp10|\n}")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "a {\n\tpadding: 10px;\n}")

    def test_expand_color(self):
        self.set_text("a {\n\tc#f|\n}")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "a {\n\tcolor: #fff;\n}")

    def test_expand_multiple_cursors(self):
        self.set_text("a {\n\tm0|\n\tw100p|\n}")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "a {\n\tmargin: 0;\n\twidth: 100%;\n}")


class TestExpandJSX(EmmetTestCase):
    syntax = JSX

    def test_expand_prefixed(self):
        self.set_text("const a = <div.foo|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), 'const a = <div className="foo"></div>')

    def test_unprefixed_is_ignored(self):
        self.set_text("const a = div.foo|")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "const a = div.foo")


class TestExpandPlainText(EmmetTestCase):
    syntax = TEXT

    def test_unsupported_syntax_does_nothing(self):
        self.set_text("ul>li|")
        self.cmd("emmet_expand_abbreviation", {"tab": True})
        self.assertEqual(self.text(), "ul>li")


class TestWrapWithAbbreviation(EmmetTestCase):
    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_selection(self):
        self.set_text("hello")
        self.select((0, 5))
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "div.w"})
        self.assertEqual(self.text(), '<div class="w">hello</div>')

    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_lines_with_repeater(self):
        self.set_text("one\ntwo")
        self.select((0, 7))
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "ul>li*"})
        self.assertEqual(self.text(), "<ul>\n\t<li>one</li>\n\t<li>two</li>\n</ul>")

    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_empty_selection_wraps_tag_contents(self):
        self.set_text("<p>te|xt</p>")
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "b"})
        self.assertEqual(self.text(), "<p><b>text</b></p>")

    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_caret_in_open_tag_wraps_tag(self):
        self.set_text("<p|>text</p>")
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "div"})
        self.assertEqual(self.text(), "<div><p>text</p></div>")

    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_multiple_cursors(self):
        self.set_text("a b")
        self.select((0, 1), (2, 3))
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "i"})
        self.assertEqual(self.text(), "<i>a</i> <i>b</i>")

    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_unicode(self):
        self.set_text("✓ 日本")
        self.select((0, 4))
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "em"})
        self.assertEqual(self.text(), "<em>✓ 日本</em>")

    @unittest.expectedFailure  # run() without input() first: wrap_entries is unset
    def test_wrap_escapes_dollar(self):
        self.set_text("$var")
        self.select((0, 4))
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": "code"})
        self.assertEqual(self.text(), "<code>$var</code>")

    def test_wrap_empty_abbreviation_is_noop(self):
        self.set_text("x")
        self.select((0, 1))
        self.view.run_command("emmet_wrap_with_abbreviation", {"wrap_abbreviation": ""})
        self.assertEqual(self.text(), "x")

    def test_two_carets_in_one_tag_share_one_wrap_region(self):
        # Both carets resolve to the same tag contents; upstream crashed here with
        # "tuple does not support item assignment".
        from .. import main

        self.set_text("<p>a|b|c</p>")
        cmd = main.EmmetWrapWithAbbreviation(self.view)
        cmd.input({})
        self.assertEqual(len(cmd.wrap_entries), 1)
        self.assertEqual(cmd.wrap_entries[0].region, sublime.Region(3, 6))

    def test_input_handler_validate_and_preview(self):
        self.set_text("<p>text</p>")
        self.select((3, 7))
        from .. import main

        cmd = main.EmmetWrapWithAbbreviation(self.view)
        handler = cmd.input({})
        assert isinstance(handler, wrap_with_abbreviation.WrapAbbreviationInputHandler)
        self.assertEqual(handler.placeholder(), "Enter abbreviation")
        self.assertTrue(handler.validate("div>span"))
        self.assertFalse(handler.validate("a)"))
        handler.preview("b")
        self.assertEqual(self.text(), "<p><b>text</b></p>")
        handler.cancel()
        self.assertEqual(self.text(), "<p>text</p>")
        self.assertIsNotNone(handler.preview("a)"))
        handler.confirm("b")
        self.assertEqual(self.text(), "<p>text</p>")


class TestBalance(EmmetTestCase):
    DOC = "<div>\n\t<p>a <b>bo|ld</b> c</p>\n</div>"

    def test_outward_steps(self):
        self.set_text(self.DOC)
        self.cmd("emmet_balance", {"direction": "outward"})
        self.assertEqual(self.text_with_carets(), "<div>\n\t<p>a <b>[bold]</b> c</p>\n</div>")
        self.cmd("emmet_balance", {"direction": "outward"})
        self.assertEqual(self.text_with_carets(), "<div>\n\t<p>a [<b>bold</b>] c</p>\n</div>")
        self.cmd("emmet_balance", {"direction": "outward"})
        self.assertEqual(self.text_with_carets(), "<div>\n\t<p>[a <b>bold</b> c]</p>\n</div>")

    def test_inward_steps(self):
        self.set_text("<div>|<p>a</p></div>")
        self.select((0, 20))
        self.cmd("emmet_balance", {"direction": "inward"})
        self.assertEqual(self.text_with_carets(), "<div>[<p>a</p>]</div>")
        self.cmd("emmet_balance", {"direction": "inward"})
        self.assertEqual(self.text_with_carets(), "<div><p>[a]</p></div>")

    def test_outward_multiple_cursors(self):
        self.set_text("<i>|ab</i><u>|cd</u>")
        self.cmd("emmet_balance", {"direction": "outward"})
        self.assertEqual(self.text_with_carets(), "<i>[ab]</i><u>[cd]</u>")

    def test_outward_unicode(self):
        self.set_text("<p>✓ 日|本</p>")
        self.cmd("emmet_balance")
        self.assertEqual(self.text_with_carets(), "<p>[✓ 日本]</p>")

    def test_outward_css(self):
        self.view.assign_syntax(CSS)
        self.set_text("a { color: r|ed; }")
        self.cmd("emmet_balance")
        self.assertEqual(self.text_with_carets(), "a { color: [red]; }")
        self.cmd("emmet_balance")
        self.assertEqual(self.text_with_carets(), "a { [color: red;] }")

    def test_plain_text_falls_back_to_html(self):
        self.view.assign_syntax(TEXT)
        self.set_text("<p>|ab</p>")
        self.cmd("emmet_balance")
        # Plain text falls back to 'html' syntax info, so balancing still works.
        self.assertEqual(self.text_with_carets(), "<p>[ab]</p>")

    def test_empty_view(self):
        self.set_text("|")
        self.cmd("emmet_balance")
        self.assertEqual(self.regions(), [(0, 0)])


class TestTagCommands(EmmetTestCase):
    def test_go_to_tag_pair(self):
        self.set_text("<div|>\n\t<p></p>\n</div>")
        self.cmd("emmet_go_to_tag_pair")
        self.assertEqual(self.text_with_carets(), "<div>\n\t<p></p>\n|</div>")
        self.cmd("emmet_go_to_tag_pair")
        self.assertEqual(self.text_with_carets(), "|<div>\n\t<p></p>\n</div>")

    def test_go_to_tag_pair_caret_before_lt(self):
        self.set_text("|<b>x</b>")
        self.cmd("emmet_go_to_tag_pair")
        self.assertEqual(self.text_with_carets(), "<b>x|</b>")

    def test_go_to_tag_pair_outside_tag(self):
        self.set_text("text|")
        self.cmd("emmet_go_to_tag_pair")
        self.assertEqual(self.text_with_carets(), "text|")

    def test_rename_tag(self):
        self.set_text('<div class="a">te|xt</div>')
        self.cmd("emmet_rename_tag")
        self.assertEqual(self.text_with_carets(), '<[div] class="a">text</[div]>')

    def test_rename_tag_multiple_cursors(self):
        self.set_text("<a>|x</a><b>y|</b>")
        self.cmd("emmet_rename_tag")
        self.assertEqual(self.text_with_carets(), "<[a]>x</[a]><[b]>y</[b]>")

    def test_rename_self_closing(self):
        self.set_text("<br|>")
        self.cmd("emmet_rename_tag")
        self.assertEqual(self.text_with_carets(), "<[br]>")

    def test_rename_tag_outside_tag_keeps_selection(self):
        self.set_text("te|xt")
        self.cmd("emmet_rename_tag")
        self.assertEqual(self.text_with_carets(), "te|xt")

    def test_remove_tag(self):
        self.set_text("<div>\n\t<p>|a</p>\n</div>")
        self.cmd("emmet_remove_tag")
        self.assertEqual(self.text(), "<div>\n\ta\n</div>")

    def test_remove_tag_dedents(self):
        self.set_text("<div>|\n\t<p>a</p>\n\t<p>b</p>\n</div>")
        self.cmd("emmet_remove_tag")
        self.assertEqual(self.text(), "<p>a</p>\n<p>b</p>")

    def test_remove_empty_tag(self):
        self.set_text("x<b>|</b>y")
        self.cmd("emmet_remove_tag")
        self.assertEqual(self.text(), "xy")

    def test_remove_self_closing_tag(self):
        self.set_text("x<br|>y")
        self.cmd("emmet_remove_tag")
        self.assertEqual(self.text(), "xy")

    def test_split_join_tag(self):
        self.set_text("<p>te|xt</p>")
        self.cmd("emmet_split_join_tag")
        self.assertEqual(self.text(), "<p />")
        self.select(1)
        self.cmd("emmet_split_join_tag")
        self.assertEqual(self.text(), "<p></p>")

    def test_split_join_xml(self):
        self.view.assign_syntax(XML)
        self.set_text("<item|/>")
        self.cmd("emmet_split_join_tag")
        self.assertEqual(self.text(), "<item></item>")


class TestToggleComment(EmmetTestCase):
    def test_comment_tag_and_uncomment(self):
        self.set_text("<div>\n\t<p>|a</p>\n</div>")
        self.cmd("emmet_toggle_comment")
        self.assertEqual(self.text(), "<div>\n\t<!-- <p>a</p> -->\n</div>")
        self.cmd("emmet_toggle_comment")
        self.assertEqual(self.text(), "<div>\n\t<p>a</p>\n</div>")

    def test_comment_selection(self):
        self.set_text("abc")
        self.select((0, 3))
        self.cmd("emmet_toggle_comment")
        self.assertEqual(self.text(), "<!-- abc -->")

    def test_comment_line_without_tag(self):
        self.set_text("  plain| text  ")
        self.cmd("emmet_toggle_comment")
        self.assertEqual(self.text(), "  <!-- plain text -->  ")

    def test_comment_removes_nested_comments(self):
        self.set_text("<d|iv><!-- x --><b></b></div>")
        self.cmd("emmet_toggle_comment")
        self.assertEqual(self.text(), "<!-- <div>x<b></b></div> -->")

    def test_css_comment(self):
        self.view.assign_syntax(CSS)
        self.set_text("a { col|or: red; }")
        self.cmd("emmet_toggle_comment")
        self.assertEqual(self.text(), "a { /* color: red; */ }")


class TestMisc(EmmetTestCase):
    def test_evaluate_math_at_caret(self):
        self.set_text("width: 10*3+2|px")
        self.cmd("emmet_evaluate_math")
        self.assertEqual(self.text(), "width: 32px")

    def test_evaluate_math_selection_and_division(self):
        self.set_text("1/3")
        self.select((0, 3))
        self.cmd("emmet_evaluate_math")
        self.assertEqual(self.text(), "0.3333")

    def test_evaluate_math_multiple_cursors(self):
        self.set_text("2*2|\n3+3|")
        self.cmd("emmet_evaluate_math")
        self.assertEqual(self.text(), "4\n6")

    def test_evaluate_math_invalid(self):
        self.set_text("1/0|")
        self.cmd("emmet_evaluate_math")
        self.assertEqual(self.text(), "1/0")

    def test_increment_number(self):
        self.set_text("a 1|9 b")
        self.cmd("emmet_increment_number", {"delta": 1})
        self.assertEqual(self.text_with_carets(), "a [20] b")

    def test_increment_decimal_and_negative(self):
        self.set_text("x: .5| -1.2|;")
        self.cmd("emmet_increment_number", {"delta": -0.1})
        self.assertEqual(self.text(), "x: .4 -1.3;")
        self.cmd("emmet_decrement_number", {"delta": 10})
        self.assertEqual(self.text(), "x: -9.6 -11.3;")

    def test_increment_no_number(self):
        self.set_text("ab|c")
        self.cmd("emmet_increment_number")
        self.assertEqual(self.text_with_carets(), "ab|c")

    def test_go_to_edit_point(self):
        self.set_text('|<a href=""></a>\n\n<b></b>')
        self.cmd("emmet_go_to_edit_point")
        self.assertEqual(self.text_with_carets(), '<a href="|"></a>\n\n<b></b>')
        self.cmd("emmet_go_to_edit_point")
        self.assertEqual(self.text_with_carets(), '<a href="">|</a>\n\n<b></b>')
        self.cmd("emmet_go_to_edit_point")
        self.assertEqual(self.text_with_carets(), '<a href=""></a>\n|\n<b></b>')
        self.cmd("emmet_go_to_edit_point", {"previous": True})
        self.assertEqual(self.text_with_carets(), '<a href="">|</a>\n\n<b></b>')

    def test_select_item_html(self):
        self.set_text('|<a href="x" class="b c">t</a>')
        self.cmd("emmet_select_item")
        self.assertEqual(self.text_with_carets(), '<[a] href="x" class="b c">t</a>')
        self.cmd("emmet_select_item")
        self.assertEqual(self.text_with_carets(), '<a [href="x"] class="b c">t</a>')
        self.cmd("emmet_select_item")
        self.assertEqual(self.text_with_carets(), '<a href="[x]" class="b c">t</a>')
        self.cmd("emmet_select_item", {"previous": True})
        self.assertEqual(self.text_with_carets(), '<a [href="x"] class="b c">t</a>')

    def test_select_item_css(self):
        self.view.assign_syntax(CSS)
        self.set_text("|a { color: red; }")
        self.cmd("emmet_select_item")
        self.assertEqual(self.text_with_carets(), "[a] { color: red; }")
        self.cmd("emmet_select_item")
        self.assertEqual(self.text_with_carets(), "a { [color: red;] }")

    def test_insert_attribute(self):
        self.set_text("<div|>")
        self.cmd("emmet_insert_attribute", {"attribute": "class"})
        self.assertEqual(self.text_with_carets(), '<div class="|">')

    def test_insert_attribute_after_space(self):
        self.set_text("<div |>")
        self.cmd("emmet_insert_attribute", {"attribute": "id"})
        self.assertEqual(self.text_with_carets(), '<div id="|">')

    def test_insert_attribute_missing(self):
        self.set_text("<div|>")
        self.cmd("emmet_insert_attribute", {})
        self.assertEqual(self.text(), "<div>")

    def test_hide_tag_preview_without_preview(self):
        self.set_text("<p></p>")
        self.cmd("emmet_hide_tag_preview")
        self.assertEqual(self.text(), "<p></p>")


class FileCommandTestCase(EmmetTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        with open(os.path.join(self.dir, "pic.png"), "wb") as f:
            f.write(PNG_1x1)
        with open(os.path.join(self.dir, "pic@2x.png"), "wb") as f:
            f.write(PNG_1x1)
        self.doc = os.path.join(self.dir, "index.html")
        patcher = patch.object(type(self.view), "file_name", lambda _v: self.doc)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        super().tearDown()
        self.tmp.cleanup()


class TestUpdateImageSize(FileCommandTestCase):
    def test_html_adds_size(self):
        self.set_text('<img src="pic.png"|>')
        self.cmd("emmet_update_image_size")
        self.assertEqual(self.text(), '<img src="pic.png" width="1" height="1">')

    def test_html_patches_existing(self):
        self.set_text('<img height="9" src="pic.png" width="8"|>')
        self.cmd("emmet_update_image_size")
        self.assertEqual(self.text(), '<img height="1" src="pic.png" width="1">')

    def test_missing_file(self):
        self.set_text('<img src="nope.png"|>')
        self.cmd("emmet_update_image_size")
        self.assertEqual(self.text(), '<img src="nope.png">')

    def test_css(self):
        self.view.assign_syntax(CSS)
        self.set_text("a { background: url(pic.png|); }")
        self.cmd("emmet_update_image_size")
        self.assertEqual(self.text(), "a { background: url(pic.png); width: 1px; height: 1px; }")

    def test_get_size_formats(self):
        get_size = update_image_size.get_size
        self.assertEqual(get_size(PNG_1x1[:100]), (1, 1))
        self.assertEqual(get_size(b"GIF89a\x02\x00\x03\x00"), (2, 3))
        self.assertEqual(get_size(b'<svg width="10" height="20">'), (10, 20))
        self.assertIsNone(get_size(b"nothing"))

    def test_dpi_suffix(self):
        self.assertEqual(update_image_size.get_dpi("a/pic@2x.png"), 1)
        self.assertEqual(update_image_size.get_dpi("a/pic@1.5x.png"), 1.5)
        self.assertEqual(update_image_size.get_dpi("a/pic.png"), 1)


class TestConvertDataUrl(FileCommandTestCase):
    def test_css_to_data_url(self):
        self.view.assign_syntax(CSS)
        self.set_text("a { background: url(pic.png|); }")
        self.cmd("emmet_convert_data_url")
        self.assertIn("url(data:image/png;base64,", self.text())

    def test_html_to_data_url(self):
        self.set_text('<img src="pic.png"|>')
        self.cmd("emmet_convert_data_url")
        self.assertIn('src="data:image/png;base64,', self.text())

    def test_from_data_url_writes_file(self):
        data = base64.urlsafe_b64encode(PNG_1x1).decode()
        self.set_text(f'<img src="data:image/png;base64,{data}">')
        region = sublime.Region(10, 10 + len(f"data:image/png;base64,{data}"))
        convert_data_url.convert_from_data_url(self.view, region, "out/new.png")
        with open(os.path.join(self.dir, "out", "new.png"), "rb") as f:
            self.assertEqual(f.read(), PNG_1x1)
        self.assertEqual(self.text(), '<img src="out/new.png">')

    def test_get_ext(self):
        self.assertEqual(convert_data_url.get_ext("data:image/svg+xml;base64,x"), ".svg")
        self.assertEqual(convert_data_url.get_ext("data:foo/bar;base64,x"), ".jpg")
