"""Abbreviation tracker and the listeners that drive it (called directly)."""

from ..lib import abbreviation, go_to_tag_pair, syntax
from ..lib.context import get_activation_context
from .helpers import CSS, HTML, JSX, PYTHON, EmmetTestCase


class TrackerTestCase(EmmetTestCase):
    emmet_settings = {"auto_mark": True, "abbreviation_preview": True}  # noqa: RUF012

    def setUp(self):
        super().setUp()
        self.marker = self.listener("AbbreviationMarkerListener")

    def type(self, chars: str) -> None:
        """Type chars one by one at the (single) caret, firing on_modified like Sublime."""
        for ch in chars:
            pos = self.view.sel()[0].b
            abbreviation.set_last_pos(self.view, pos)
            self.view.run_command("insert", {"characters": ch})
            self.marker.on_modified(self.view)

    def tracker(self) -> abbreviation.AbbreviationTracker | None:
        return abbreviation.get_tracker(self.view)

    def active(self) -> abbreviation.AbbreviationTracker:
        trk = abbreviation.get_tracker(self.view)
        assert trk is not None, "no active tracker"
        return trk


class TestTracker(TrackerTestCase):
    def test_typing_starts_and_extends_tracker(self):
        self.set_text("<div>\n\t|\n</div>")
        self.type("ul>li")
        trk = self.active()
        self.assertEqual(trk.abbreviation, "ul>li")
        self.assertIsInstance(trk, abbreviation.AbbreviationTrackerValid)
        self.assertEqual(self.view.get_regions(abbreviation.ABBR_REGION_ID), [trk.region])
        self.assertIn("<li></li>", trk.preview)

    def test_tab_expands_tracked_abbreviation(self):
        self.set_text("|")
        self.type("p.x")
        self.assertTrue(
            self.marker.on_query_context(self.view, "emmet_abbreviation", 0, True, False)
        )
        self.cmd("emmet_expand_abbreviation", {"tab": True})
        self.assertEqual(self.text(), '<p class="x"></p>')
        self.assertIsNone(self.tracker())

    def test_not_started_inside_word(self):
        self.set_text("hello|")
        self.type("x")
        self.assertIsNone(self.tracker())

    def test_not_started_in_tag(self):
        self.set_text("<div |></div>")
        self.type("a")
        self.assertIsNone(self.tracker())

    def test_not_started_when_not_typing(self):
        self.set_text("|")
        # last_pos does not precede the caret: e.g. a paste or a jump.
        self.view.run_command("insert", {"characters": "ul"})
        abbreviation.set_last_pos(self.view, 0)
        self.marker.on_modified(self.view)
        self.assertIsNone(self.tracker())

    def test_auto_mark_disabled(self):
        self.settings.set("auto_mark", False)
        self.set_text("|")
        self.type("ul")
        self.assertIsNone(self.tracker())

    def test_auto_mark_stylesheet_only(self):
        self.settings.set("auto_mark", "stylesheet")
        self.set_text("|")
        self.type("ul")
        self.assertIsNone(self.tracker())

    def test_invalid_last_char_stops_tracking(self):
        self.set_text("|")
        self.type("a)")
        self.assertIsNone(self.tracker())

    def test_error_tracker_and_preview(self):
        self.set_text("a)b")
        config = get_activation_context(self.view, 0)
        trk = abbreviation.start_tracking(self.view, 0, 3, {"config": config, "forced": True})
        assert isinstance(trk, abbreviation.AbbreviationTrackerError)
        assert trk.error is not None
        self.assertEqual(trk.error["pos"], 1)
        self.assertEqual(trk.error["pointer"], "-^")
        abbreviation.show_preview(self.view, trk)
        abbreviation.hide_preview(self.view)

    def test_typing_after_space_stops_tracker(self):
        self.set_text("|")
        self.type("ul")
        self.assertIsNotNone(self.tracker())
        self.type(" ")
        self.assertIsNone(self.tracker())

    def test_backspace_shrinks_tracker(self):
        self.set_text("|")
        self.type("ul>li")
        pos = self.view.sel()[0].b
        abbreviation.set_last_pos(self.view, pos)
        self.view.run_command("left_delete")
        self.marker.on_modified(self.view)
        self.assertEqual(self.active().abbreviation, "ul>l")

    def test_unicode_before_abbreviation(self):
        self.set_text("✓ 日本 |")
        self.type("b")
        self.assertEqual(self.active().abbreviation, "b")
        self.cmd("emmet_expand_abbreviation", {"tab": True})
        self.assertEqual(self.text(), "✓ 日本 <b></b>")

    def test_crlf_view(self):
        self.view.set_line_endings("windows")
        self.set_text("<div>\n|\n</div>")
        self.type("span")
        self.assertEqual(self.active().abbreviation, "span")

    def test_selection_leaving_and_restoring(self):
        self.set_text("x |")
        self.type("ul>li")
        trk = self.active()
        self.select(0)
        self.marker.on_selection_modified(self.view)
        # Moving the caret out keeps the tracker but hides the preview.
        self.assertIs(self.tracker(), trk)
        # Stopping without force keeps it in the cache...
        abbreviation.stop_tracking(self.view)
        self.assertIsNone(self.tracker())
        # ...so coming back restores it.
        self.select(trk.region.b)
        self.marker.on_selection_modified(self.view)
        self.assertEqual(self.active().abbreviation, "ul>li")

    def test_on_activated_and_close(self):
        self.set_text("|")
        self.type("ul")
        self.marker.on_activated(self.view)
        self.marker.on_close(self.view)
        self.assertIsNone(self.tracker())

    def test_widget_views_are_ignored(self):
        self.view.settings().set("is_widget", True)
        try:
            self.set_text("|")
            self.type("ul")
            self.assertIsNone(self.tracker())
        finally:
            self.view.settings().erase("is_widget")

    def test_multiple_cursors_context(self):
        self.set_text("ul|\nol|\n")
        self.assertTrue(
            self.marker.on_query_context(self.view, "emmet_activation_scope", 0, True, False)
        )
        self.assertTrue(
            self.marker.on_query_context(self.view, "emmet_multicursor_tab_expand", 0, True, False)
        )
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "<ul></ul>\n<ol></ol>\n")

    def test_multicursor_tab_setting_off(self):
        self.settings.set("multicursor_tab", False)
        self.set_text("ul|\nol|")
        self.assertFalse(
            self.marker.on_query_context(self.view, "emmet_multicursor_tab_expand", 0, True, False)
        )

    def test_query_context_keys(self):
        self.set_text("|")
        q = self.marker.on_query_context
        self.assertFalse(q(self.view, "has_emmet_abbreviation_mark", 0, True, False))
        self.assertFalse(q(self.view, "has_emmet_forced_abbreviation_mark", 0, True, False))
        self.assertFalse(q(self.view, "emmet_abbreviation", 0, True, False))
        self.type("ul")
        self.assertTrue(q(self.view, "has_emmet_abbreviation_mark", 0, True, False))
        self.assertTrue(q(self.view, "emmet_capture_abbreviation", 0, True, False))
        self.assertIsNone(q(self.view, "unknown_key", 0, True, False))
        self.settings.set("tab_expand", False)
        self.assertFalse(q(self.view, "emmet_tab_expand", 0, True, False))
        self.settings.set("auto_id_class", True)
        self.assertTrue(q(self.view, "emmet_auto_id_class", 0, True, False))

    def test_unknown_single_word_is_not_candidate(self):
        # known_snippets_only is on for html: `foo` is not a known tag.
        self.set_text("|")
        self.type("foo")
        trk = self.tracker()
        self.assertTrue(trk is None or not trk.valid_candidate)
        self.assertFalse(
            self.marker.on_query_context(self.view, "emmet_abbreviation", 0, True, False)
        )

    def test_on_query_completions(self):
        self.set_text("|")
        self.view.run_command("insert", {"characters": "ul>li"})
        self.marker.on_text_command(self.view, "auto_complete", {})
        self.assertTrue(self.marker.pending_completions_request)
        items = self.marker.on_query_completions(self.view, "li", [self.view.size()])
        self.assertEqual(len(items), 1)
        self.assertIn("<ul>", items[0][1])
        self.assertFalse(self.marker.pending_completions_request)
        # Without a pending request nothing is returned.
        self.assertIsNone(self.marker.on_query_completions(self.view, "li", [self.view.size()]))

    def test_post_text_command(self):
        self.set_text("|")
        self.marker.pending_completions_request = True
        self.marker.on_post_text_command(self.view, "auto_complete", {})
        self.assertFalse(self.marker.pending_completions_request)
        self.type("ul")
        self.marker.on_text_command(self.view, "commit_completion", {})
        self.assertIsNone(self.tracker())
        self.marker.on_post_text_command(self.view, "undo", {})

    def test_undo_restores_marker(self):
        self.set_text("|")
        self.type("ul")
        self.cmd("emmet_expand_abbreviation", {"tab": True})
        self.view.run_command("undo")
        self.marker.on_post_text_command(self.view, "undo", {})


class TestForcedAbbreviation(TrackerTestCase):
    def test_enter_abbreviation_mode_and_expand(self):
        self.set_text("text |")
        self.cmd("emmet_enter_abbreviation")
        trk = self.active()
        self.assertTrue(trk.forced)
        self.assertTrue(
            self.marker.on_query_context(
                self.view, "has_emmet_forced_abbreviation_mark", 0, True, False
            )
        )
        self.type("b")
        self.cmd("emmet_expand_abbreviation")
        self.assertEqual(self.text(), "text <b></b>")

    def test_enter_abbreviation_from_selection(self):
        self.set_text("ul>li")
        self.select((0, 5))
        self.cmd("emmet_enter_abbreviation")
        self.assertEqual(self.active().abbreviation, "ul>li")

    def test_toggle_off_removes_text(self):
        self.set_text("|")
        self.cmd("emmet_enter_abbreviation")
        self.type("em")
        self.cmd("emmet_enter_abbreviation")
        self.assertIsNone(self.tracker())
        self.assertEqual(self.text(), "")

    def test_capture_abbreviation(self):
        self.set_text("div>p|")
        self.cmd("emmet_capture_abbreviation")
        self.assertEqual(self.active().abbreviation, "div>p")


class TestCSSTracker(TrackerTestCase):
    syntax = CSS

    def test_css_property_tracking(self):
        self.set_text("a {\n\t|\n}")
        self.type("p10")
        trk = self.active()
        self.assertEqual(trk.config.type, "stylesheet")
        self.cmd("emmet_expand_abbreviation", {"tab": True})
        self.assertEqual(self.text(), "a {\n\tpadding: 10px;\n}")

    def test_css_value_hash_is_not_auto_tracked(self):
        # `#` is not a stylesheet abbreviation start (re_stylesheet_word_bound).
        self.set_text("a { color: |; }")
        self.type("#f")
        self.assertIsNone(self.tracker())

    def test_css_plain_value_not_tracked(self):
        self.set_text("a { color: |; }")
        self.type("r")
        self.assertIsNone(self.tracker())


class TestJSXTracker(TrackerTestCase):
    syntax = JSX

    def test_prefixed_abbreviation(self):
        self.set_text("const a = |")
        self.type("<div")
        self.assertEqual(self.active().abbreviation, "div")

    def test_unprefixed_not_tracked(self):
        self.set_text("const a = |")
        self.type("div")
        self.assertIsNone(self.tracker())


class TestUnrelatedSyntax(TrackerTestCase):
    syntax = PYTHON

    def test_no_tracking_in_python(self):
        self.set_text("x = 1\n|")
        self.type("ul>li")
        self.assertIsNone(self.tracker())
        self.assertIsNone(syntax.from_pos(self.view, 0))

    def test_tab_context_false(self):
        self.set_text("ul|")
        self.assertFalse(
            self.marker.on_query_context(self.view, "emmet_activation_scope", 0, True, False)
        )


class TestTagPreview(EmmetTestCase):
    syntax = HTML
    emmet_settings = {"tag_preview": True, "tag_preview_size_limit": 0}  # noqa: RUF012

    def setUp(self):
        super().setUp()
        self.preview = self.listener("PreviewTagPair")

    def test_preview_shown_when_open_tag_offscreen(self):
        body = "\n".join(f"<p>{i}</p>" for i in range(400))
        self.set_text(f'<div class="a b" id="x" title="t">\n{body}\n</div|>')
        # The output panel shows nothing, so the open tag is never visible.
        self.preview.on_selection_modified_async(self.view)
        self.assertTrue(go_to_tag_pair.has_preview(self.view))
        self.assertTrue(
            self.preview.on_query_context(self.view, "emmet_tag_preview", 0, True, False)
        )
        self.cmd("emmet_hide_tag_preview")
        self.assertFalse(go_to_tag_pair.has_preview(self.view))
        self.select(1)
        self.preview.on_selection_modified_async(self.view)
        self.assertFalse(go_to_tag_pair.has_preview(self.view))

    def test_preview_text(self):
        ctx = {"name": "div", "attributes": {"class": " a  b ", "id": "x", "title": "t"}}
        self.assertEqual(go_to_tag_pair.create_tag_preview(ctx), 'div#x.a.b[title="t"]')

    def test_no_preview_without_attributes(self):
        self.set_text("<div>\n</div|>")
        self.preview.on_selection_modified_async(self.view)
        self.assertFalse(go_to_tag_pair.has_preview(self.view))

    def test_size_limit(self):
        self.settings.set("tag_preview_size_limit", 5)
        self.set_text('<div class="a">\n</div|>')
        self.preview.on_selection_modified_async(self.view)
        self.assertFalse(go_to_tag_pair.has_preview(self.view))

    def test_other_query_context(self):
        self.assertIsNone(self.preview.on_query_context(self.view, "other", 0, True, False))

    def test_close_tag_precheck_never_skips_a_preview(self):
        # may_be_in_close_tag() must be a necessary condition for the full match:
        # wherever the matched close tag contains the caret, it returns True.
        from ..lib import emmet_sublime

        doc = '<div a="1">\n <p>x</p>\n <br/>\n <span >y</span >\n</div>\n<ul><li>z</li></ul>'
        self.set_text(doc)
        for pt in range(self.view.size() + 1):
            ctx = emmet_sublime.get_tag_context(self.view, pt)
            if ctx and "close" in ctx and ctx["close"].contains(pt):
                self.assertTrue(go_to_tag_pair.may_be_in_close_tag(self.view, pt), pt)
        self.assertFalse(go_to_tag_pair.may_be_in_close_tag(self.view, 13))
        self.assertTrue(go_to_tag_pair.may_be_in_close_tag(self.view, doc.index("</p>")))
