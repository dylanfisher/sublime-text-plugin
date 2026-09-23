"""Smaller units: syntax/config helpers, CSS context detection, previews, telemetry,
image-size parsing and the utils module."""

import os
import struct
import tempfile
from unittest.mock import MagicMock, patch

import sublime

from ..lib import (
    abbreviation,
    comment,
    config,
    context,
    html_highlight,
    inc_dec_number,
    syntax,
    telemetry,
    update_image_size,
    utils,
)
from .helpers import CSS, HTML, JSX, PYTHON, EmmetTestCase


class TestSyntax(EmmetTestCase):
    def test_from_pos_and_info(self):
        self.set_text("<p></p>")
        self.assertEqual(syntax.from_pos(self.view, 0), "html")
        self.assertEqual(syntax.info(self.view, 0), {"syntax": "html", "type": "markup"})
        self.view.assign_syntax(PYTHON)
        self.assertIsNone(syntax.info(self.view, 0))
        self.assertEqual(syntax.info(self.view, 0, "css"), {"syntax": "css", "type": "stylesheet"})

    def test_predicates(self):
        self.assertTrue(syntax.is_xml("xsl"))
        self.assertTrue(syntax.is_html("xml"))
        self.assertFalse(syntax.is_html(None))
        self.assertTrue(syntax.is_supported("stylus"))
        self.assertFalse(syntax.is_css("sass"))
        self.assertEqual(syntax.get_type("sass"), "stylesheet")
        self.assertEqual(syntax.get_type(None), "markup")

    def test_doc_syntax(self):
        self.assertEqual(syntax.doc_syntax(self.view), "html")
        self.view.assign_syntax(JSX)
        self.assertEqual(syntax.doc_syntax(self.view), "jsx")

    def test_inline_scope(self):
        self.set_text('<p style="color: red"></p>')
        self.assertTrue(syntax.is_inline(self.view, 12))
        self.assertFalse(syntax.is_inline(self.view, 1))

    def test_bad_syntax_scopes_setting(self):
        self.settings.set("syntax_scopes", ["not", "a", "dict"])
        self.set_text("<p></p>")
        self.assertIsNone(syntax.from_pos(self.view, 0))

    def test_ignore_scopes(self):
        self.settings.set("ignore_scopes", ["text.html"])
        try:
            self.set_text("ul")
            self.assertFalse(syntax.in_activation_scope(self.view, 2))
        finally:
            self.settings.erase("ignore_scopes")

    def test_activation_scope_before_lt(self):
        self.set_text("<div>a</div>")
        self.assertTrue(syntax.in_activation_scope(self.view, 6))


class TestConfig(EmmetTestCase):
    def test_fields(self):
        self.assertEqual(config.field(1, "x"), "${1:x}")
        self.assertEqual(config.field(2, ""), "${2}")
        self.assertEqual(config.field_preview(1, "x"), "x")

    def test_output_options_comment_and_bem(self):
        self.settings.set("comment", True)
        self.settings.set("bem", True)
        try:
            opt = config.get_output_options(self.view)
            self.assertTrue(opt["comment.enabled"])
            self.assertIn("comment.after", opt)
            self.assertTrue(opt["bem.enabled"])
            self.assertEqual(opt["output.selfClosingStyle"], self.settings.get("markup_style"))
        finally:
            self.settings.erase("comment")
            self.settings.erase("bem")

    def test_user_css_and_cache_reset(self):
        self.assertIsInstance(config.get_user_css(), str)
        config.emmet_cache["x"] = 1
        config.handle_settings_change()
        self.assertNotIn("x", config.emmet_cache)

    def test_jsx_config(self):
        self.view.assign_syntax(JSX)
        self.set_text("x")
        cfg = config.get_config(self.view, 0)
        self.assertEqual(cfg.syntax, "jsx")
        self.assertTrue(cfg.options["jsx.enabled"])


class TestCSSContext(EmmetTestCase):
    syntax = CSS

    def test_property_context(self):
        self.assertEqual(context.get_css_context_from_text("a { p }", 5), {"name": "@@global"})

    def test_value_context_only_for_colors(self):
        self.assertIsNone(context.get_css_context_from_text("a { color: r }", 12))
        self.assertIsNotNone(context.get_css_context_from_text("a { color: #f }", 13))

    def test_nested_selector(self):
        text = "a {\n  b\n}"
        self.assertEqual(context.get_css_context_from_text(text, 7), {"name": "@@global"})

    def test_media_expression(self):
        self.assertTrue(context.in_media_expression("@media (min-w)", 9))
        self.assertFalse(context.in_media_expression("@media screen", 9))
        text = "@media (w) {}"
        self.assertEqual(context.get_css_context_from_text(text, 8), {"name": "@@property"})

    def test_no_context_outside(self):
        self.assertIsNone(context.get_css_context_from_text("", 0))

    def test_fast_context_in_media_query(self):
        self.set_text("@media (m) {\n}")
        self.assertIsNotNone(context.get_activation_context(self.view, 9))

    def test_matching_section_equals_full_scan(self):
        self.set_text("a {\n  color: red;\n}\n  b, c { margin: 0 }\n@media (x) { d { e: f } }\n")
        size = self.view.size()
        trimmed = [
            context._trim_section(self.view, r, size)
            for r in self.view.find_by_selector("meta.selector, meta.property-list")
        ]
        for pt in range(size + 1):
            expected = next((r for r in trimmed if r.contains(pt)), None)
            self.assertEqual(context.get_matching_section(self.view, pt), expected, pt)

    def test_scss_uses_text_scanner(self):
        self.set_text("a {\n  m\n}")
        with patch.object(syntax, "doc_syntax", return_value="scss"):
            self.assertEqual(context.get_css_context(self.view, 7), {"name": "@@global"})

    def test_css_section_typing_at_top_level(self):
        self.set_text("a")
        cfg = context.get_activation_context(self.view, 1)
        assert cfg is not None
        self.assertEqual(cfg.context, {"name": "@@section"})

    def test_inline_style_attribute(self):
        self.view.assign_syntax(HTML)
        self.set_text('<p style="c"></p>')
        cfg = context.get_activation_context(self.view, 11)
        self.assertIsNotNone(cfg)
        assert cfg is not None
        self.assertEqual(cfg.context, {"name": "@@property"})


class TestHTMLContext(EmmetTestCase):
    def test_parent_tag_context(self):
        self.set_text('<ul class="x">\n\t\n</ul>')
        ctx = context.get_html_context(self.view, 16)
        self.assertEqual(ctx, {"name": "ul", "attributes": {"class": "x"}})

    def test_tag_without_attributes(self):
        self.set_text("<ol><li></li>\n</ol>")
        ctx = context.get_html_context(self.view, 13)
        self.assertEqual(ctx, {"name": "ol", "attributes": {}})

    def test_self_closing_are_skipped(self):
        self.set_text('<div><br/><img src="a"> <input>|</div>')
        ctx = context.get_html_context(self.view, 24)
        self.assertEqual(ctx and ctx["name"], "div")

    def test_inside_tag_or_comment(self):
        self.set_text("<div class></div><!-- c -->")
        self.assertIsNone(context.get_html_context(self.view, 6))
        self.assertIsNone(context.get_html_context(self.view, 22))

    def test_top_level(self):
        self.set_text("text")
        self.assertEqual(context.get_html_context(self.view, 2), {})


class TestPreviews(EmmetTestCase):
    emmet_settings = {"abbreviation_preview": True}  # noqa: RUF012

    def track(self, text, pos, syntax_path=HTML):
        self.view.assign_syntax(syntax_path)
        self.set_text(text)
        return abbreviation.suggest_abbreviation_tracker(self.view, pos, True)

    def test_markup_popup_preview(self):
        trk = self.track('ul>li[title="a"]', 16)
        assert trk is not None
        self.assertFalse(trk.simple)
        abbreviation.show_preview(self.view, trk)
        self.assertTrue(abbreviation._has_popup_preview.get(self.view.id()))
        abbreviation.hide_preview(self.view)
        self.assertFalse(abbreviation._has_popup_preview.get(self.view.id()))

    def test_simple_abbreviation_has_no_preview(self):
        trk = self.track("span", 4)
        assert trk is not None
        self.assertTrue(trk.simple)
        abbreviation.show_preview(self.view, trk)
        self.assertFalse(abbreviation._has_popup_preview.get(self.view.id()))

    def test_css_phantom_preview(self):
        trk = self.track("a {\n\tp10\n}", 8, CSS)
        assert trk is not None
        abbreviation.show_preview(self.view, trk)
        self.assertIn(self.view.id(), abbreviation._phantom_preview)
        abbreviation.hide_preview(self.view)
        self.assertNotIn(self.view.id(), abbreviation._phantom_preview)

    def test_preview_disabled_by_type(self):
        self.settings.set("abbreviation_preview", "stylesheet")
        trk = self.track("ul>li", 5)
        assert trk is not None
        self.assertFalse(abbreviation.is_preview_enabled(trk))

    def test_jsx_preview_is_escaped(self):
        trk = self.track("<ul>li", 6, JSX)
        assert trk is not None
        abbreviation.show_preview(self.view, trk)
        abbreviation.hide_preview(self.view)

    def test_forced_indicator(self):
        self.set_text("x")
        trk = abbreviation.start_tracking(self.view, 0, 1, {"forced": True})
        assert trk is not None
        self.assertIn(self.view.id(), abbreviation._forced_indicator)

    def test_highlight(self):
        out = html_highlight.highlight('<a href="x" hidden>t</a>')
        self.assertIn('<span class="attr-name">href</span>', out)
        self.assertIn('<span class="tag close">', out)
        self.assertIn("hidden", out)
        self.assertIn(".dark", html_highlight.styles())

    def test_format_snippet(self):
        self.assertEqual(abbreviation.indent_size("\t\tx", 20), 40)
        self.assertIn('class="c"', abbreviation.format_snippet("a", "c"))

    def test_get_by_key(self):
        self.assertEqual(abbreviation.get_by_key({"a": {"b": 1}}, "a.b"), 1)
        self.assertEqual(abbreviation.get_by_key(None, "a", 5), 5)
        self.assertEqual(abbreviation.get_by_key({"a": None}, ["a", "b"], 2), 2)

    def test_update_region(self):
        r = sublime.Region(5, 8)
        abbreviation.update_region(r, -1, 5)
        self.assertEqual((r.a, r.b), (4, 7))
        r = sublime.Region(5, 8)
        abbreviation.update_region(r, -1, 7)
        self.assertEqual((r.a, r.b), (5, 7))
        r = sublime.Region(5, 8)
        abbreviation.update_region(r, 2, 6)
        self.assertEqual((r.a, r.b), (5, 10))

    def test_is_valid_tracker_for_errors(self):
        self.set_text("a)b(")
        cfg = context.get_activation_context(self.view, 0)
        trk = abbreviation.create_tracker(
            self.view, sublime.Region(0, 4), {"config": cfg, "forced": True}
        )
        assert trk is not None
        self.assertFalse(abbreviation.is_valid_tracker(trk, sublime.Region(0, 4), 4))
        self.assertTrue(abbreviation.is_valid_tracker(trk, sublime.Region(0, 4), 2))
        trk.abbreviation = "a</b"
        self.assertFalse(abbreviation.is_valid_tracker(trk, sublime.Region(0, 4), 2))

    def test_plugin_unloaded_unmarks(self):
        abbreviation.plugin_unloaded()


class TestCommentHelpers(EmmetTestCase):
    def test_embedded_css_comment(self):
        self.set_text("<style>\na { color: red; }\n</style>")
        pt = 12
        region = comment.get_range_for_comment(self.view, pt)
        self.assertIsNotNone(region)
        assert region is not None
        self.assertEqual(self.view.substr(region), "a { color: red; }")

    def test_toggle_comment_listener(self):
        listener = self.listener("ToggleCommentListener")
        self.set_text("<p>|</p>")
        self.settings.set("toggle_comment", True)
        self.assertEqual(
            listener.on_text_command(self.view, "toggle_comment", {}),
            ("emmet_toggle_comment", None),
        )
        self.assertIsNone(listener.on_text_command(self.view, "other", {}))
        self.settings.set("toggle_comment", False)
        self.assertIsNone(listener.on_text_command(self.view, "toggle_comment", {}))

    def test_get_comment_regions_unclosed(self):
        self.set_text("<!-- a --> <!-- b")
        found = comment.get_comment_regions(
            self.view, sublime.Region(0, self.view.size()), comment.html_comment
        )
        self.assertEqual([(r.a, r.b) for r in found], [(0, 10)])

    def test_remove_comments_not_a_comment(self):
        self.set_text("a|bc")
        self.view.run_command("emmet_toggle_comment")  # comments the line
        self.assertEqual(self.text(), "<!-- abc -->")


class TestIncDec(EmmetTestCase):
    def test_extract_number(self):
        self.assertEqual(inc_dec_number.extract_number("a -1.5 b", 4), (2, 6))
        self.assertEqual(inc_dec_number.extract_number("1.2.3", 1), (0, 3))
        self.assertIsNone(inc_dec_number.extract_number("abc", 1))

    def test_update_number(self):
        self.assertEqual(inc_dec_number.update_number("9", 1), "10")
        self.assertEqual(inc_dec_number.update_number("-.5", 0.1), "-.4")
        self.assertEqual(inc_dec_number.update_number("0.1", -0.2), "-0.1")
        self.assertIsNone(inc_dec_number.update_number("x", 1))

    def test_selected_text_not_number(self):
        self.set_text("abc")
        self.select((0, 3))
        self.cmd("emmet_increment_number", {"delta": 1})
        self.assertEqual(self.text(), "abc")


class TestUtils(EmmetTestCase):
    def test_preprocess_snippet(self):
        self.assertEqual(utils.preprocess_snippet("${1:a} $x \\$y"), "${1:a} \\$x \\$y")
        self.assertEqual(utils.escape_snippet("$a"), "\\$a")

    def test_is_url_and_quoted(self):
        self.assertTrue(utils.is_url("https://x/y.png"))
        self.assertFalse(utils.is_url("img/y.png"))
        self.assertTrue(utils.is_quoted('"a"'))
        self.assertTrue(utils.is_quoted("{a}"))
        self.assertFalse(utils.is_quoted(""))
        self.assertFalse(utils.is_quoted(None))
        self.assertTrue(utils.has_new_line("a\r"))

    def test_locate_and_create_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "a", "b"))
            img = os.path.join(tmp, "img.png")
            with open(img, "wb") as f:
                f.write(b"x")
            doc = os.path.join(tmp, "a", "b", "doc.html")
            # Absolute-looking paths are searched upwards from the document.
            self.assertEqual(utils.locate_file(doc, "/img.png"), os.path.normpath(img))
            self.assertIsNone(utils.locate_file(doc, "missing.png"))
            self.assertEqual(utils.create_path(img, "c.png"), os.path.join(tmp, "c.png"))
            self.assertEqual(utils.create_path(os.path.join(tmp, "nope"), "c.png"), "")
            self.assertEqual(utils.read_file(img), b"x")

    def test_narrow_to_non_space(self):
        self.set_text("  ab  ")
        r = utils.narrow_to_non_space(self.view, sublime.Region(0, 6))
        self.assertEqual((r.a, r.b), (2, 4))
        r = utils.narrow_to_non_space(self.view, sublime.Region(0, 6), utils.NON_SPACE_LEFT)
        self.assertEqual((r.a, r.b), (2, 6))

    def test_get_caret_without_selection(self):
        self.set_text("x")
        self.view.sel().clear()
        self.assertEqual(utils.get_caret(self.view), 0)


def gif(w, h):
    return b"GIF89a" + struct.pack("<HH", w, h)


class TestImageSize(EmmetTestCase):
    def test_formats(self):
        get = update_image_size.get_size
        self.assertEqual(get(gif(3, 4)), (3, 4))
        png_old = b"\211PNG\r\n\032\n" + struct.pack(">LL", 5, 6)
        self.assertEqual(get(png_old), (5, 6))
        webp_lossy = b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 10 + struct.pack("<HH", 7, 8)
        self.assertEqual(get(webp_lossy), (7, 8))
        bits = (9 - 1) | ((10 - 1) << 14)
        webp_ll = b"RIFF\0\0\0\0WEBPVP8L" + b"\0" * 5 + struct.pack("<I", bits) + b"\0" * 5
        self.assertEqual(get(webp_ll), (9, 10))
        webp_x = bytearray(b"RIFF\0\0\0\0WEBPVP8X" + b"\0" * 14)
        webp_x[24], webp_x[27] = 10, 20
        self.assertEqual(get(bytes(webp_x)), (11, 21))
        webp_other = b"RIFF\0\0\0\0WEBPXXXX" + b"\0" * 14
        self.assertEqual(get(webp_other), (0, 0))
        jpeg = (
            b"\377\330\377\340"
            + struct.pack(">H", 4)
            + b"\0\0"
            + b"\377\300"
            + b"\0\0\0"
            + struct.pack(">HH", 12, 34)
        )
        self.assertEqual(get(jpeg), (34, 12))
        self.assertEqual(get(b'<svg height="7">'), (0, 7))

    def test_css_patch_existing_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "p.gif"), "wb") as f:
                f.write(gif(3, 4))
            doc = os.path.join(tmp, "a.css")
            self.view.assign_syntax(CSS)
            with patch.object(type(self.view), "file_name", lambda _v: doc):
                self.set_text("a { width: 1px; background: url(p.gif|); height: 2px; }")
                self.cmd("emmet_update_image_size")
                self.assertEqual(
                    self.text(), "a { width: 3px; background: url(p.gif); height: 4px; }"
                )
                self.set_text("a { background: url(p.gif|); width: 1px; }")
                self.cmd("emmet_update_image_size")
                self.assertEqual(
                    self.text(), "a { background: url(p.gif); width: 3px; height: 4px; }"
                )

    def test_html_single_existing_attribute(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "p.gif"), "wb") as f:
                f.write(gif(3, 4))
            doc = os.path.join(tmp, "a.html")
            with patch.object(type(self.view), "file_name", lambda _v: doc):
                self.set_text('<img src="p.gif" width="9"|>')
                self.cmd("emmet_update_image_size")
                self.assertEqual(self.text(), '<img src="p.gif" width="3" height="4">')
                self.set_text('<img width="9" height="1" src="p.gif"|>')
                self.cmd("emmet_update_image_size")
                self.assertEqual(self.text(), '<img width="3" height="4" src="p.gif">')

    def test_unsaved_view_and_unknown_format(self):
        self.set_text('<img src="p.gif"|>')
        self.cmd("emmet_update_image_size")  # no file name: nothing to resolve against
        self.assertEqual(self.text(), '<img src="p.gif">')
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "p.png"), "wb") as f:
                f.write(b"not an image")
            doc = os.path.join(tmp, "a.html")
            with patch.object(type(self.view), "file_name", lambda _v: doc):
                self.set_text('<img src="p.png"|>')
                self.cmd("emmet_update_image_size")
                self.assertEqual(self.text(), '<img src="p.png">')


class TestTelemetry(EmmetTestCase):
    def setUp(self):
        super().setUp()
        self._queue = list(telemetry.queue)
        telemetry.queue.clear()

    def tearDown(self):
        telemetry.queue[:] = self._queue
        super().tearDown()

    def test_track_action_respects_setting(self):
        with patch.object(telemetry, "get_settings", return_value=False):
            telemetry.track_action("A")
        self.assertEqual(telemetry.queue, [])

    def test_queue_and_flush(self):
        with patch.object(telemetry.sublime, "set_timeout_async") as later:
            telemetry.send_tracking_action("A", "label", "1")
            self.assertTrue(later.called)
        self.assertEqual(telemetry.queue[0]["el"], "label")
        opener = MagicMock()
        with patch.object(telemetry.urllib.request, "urlopen", opener):
            telemetry._flush_queue()
        self.assertEqual(telemetry.queue, [])
        req = opener.call_args[0][0]
        self.assertEqual(req.full_url, telemetry.HOST)
        self.assertIn("EmmetTracker/", req.headers["User-agent"])

    def test_flush_handles_network_errors(self):
        telemetry.queue.append({"t": "event"})
        with patch.object(telemetry.urllib.request, "urlopen", side_effect=OSError("down")):
            telemetry._flush_queue()  # must not raise
        self.assertEqual(telemetry.queue, [])
        telemetry.scheduled = False
        telemetry._flush_queue()  # empty queue: nothing to do

    def test_check_telemetry_existing_settings_does_nothing(self):
        fake = MagicMock()
        fake.get.side_effect = {"uid": "abc", "telemetry": False}.get
        with (
            patch.object(telemetry.sublime, "load_settings", return_value=fake),
            patch.object(telemetry.sublime, "save_settings") as save,
            patch.object(telemetry, "ask_for_telemetry") as ask,
        ):
            telemetry.check_telemetry()
        save.assert_not_called()
        ask.assert_not_called()
        self.assertEqual(telemetry.queue, [])

    def test_check_telemetry_first_run(self):
        fake = MagicMock()
        fake.get.side_effect = lambda k, d=None: None
        with (
            patch.object(telemetry.sublime, "load_settings", return_value=fake),
            patch.object(telemetry.sublime, "save_settings") as save,
            patch.object(telemetry, "ask_for_telemetry", return_value=False),
            patch.object(telemetry.sublime, "set_timeout_async"),
        ):
            telemetry.check_telemetry()
        save.assert_called_once_with("Emmet.sublime-settings")
        fake.set.assert_any_call("telemetry", False)
