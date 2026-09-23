# Performance

Benchmarks live in `tests/benchmarks/` (`bench_emmet.py`, run one case at one
fixture size per Sublime call; `run_all.sh` runs them all and merges the JSON).
Fixtures are generated, never committed: an HTML page (a `<div>` block with
attributes, a paragraph, an inline list, an `<img>` and a blank line, repeated), a
CSS file, a JSX file and a Python file, at 200 ("small"), 10,000 and 100,000 lines.

Listener rows call Emmet's listener objects directly while its real listeners are
detached, so they time only Emmet's own work for one event. The user's settings
apply (`auto_mark` on, `abbreviation_preview` off); "tag preview on" rows turn
`tag_preview` on and `tag_preview_size_limit` off in memory.

"Before" is upstream v2.4.5 (with the same vendored py-emmet 1.3.1); "After" is this
fork. Both columns were measured back to back in one session (the CSS and
`on_activated` rows in a second back-to-back pair).

Sublime Text build 4213, Python 3.14.6, macOS 26.6.2, Apple M5 Max. Median of 20 runs after 3 warm-ups.

| Benchmark | Before | After | Change |
|---|---:|---:|---:|
| load: Emmet.main | 5.798 ms | 5.805 ms | +0.1% |
| on_modified: type 1st abbr char (css 10k) | 30.360 ms | 3.326 ms | -89.0% |
| on_modified: type 1st abbr char (html small) | 2.088 ms | 0.589 ms | -71.8% |
| on_modified: type 1st abbr char (html 10k) | 88.469 ms | 10.590 ms | -88.0% |
| on_modified: type 1st abbr char (html 100k) | 885.563 ms | 108.693 ms | -87.7% |
| on_modified: type 1st abbr char (jsx 10k) | 0.312 ms | 0.310 ms | -0.7% |
| on_modified: type 1st abbr char (python 10k) | 0.088 ms | 0.088 ms | +0.6% |
| on_modified: type 2nd abbr char (html small) | 0.164 ms | 0.168 ms | +2.2% |
| on_modified: type 2nd abbr char (html 10k) | 0.167 ms | 0.144 ms | -13.9% |
| on_modified: type 2nd abbr char (html 100k) | 0.175 ms | 0.171 ms | -2.1% |
| on_modified: type inside a tag (html small) | 0.094 ms | 0.093 ms | -1.1% |
| on_modified: type inside a tag (html 10k) | 0.102 ms | 0.092 ms | -9.4% |
| on_modified: type inside a tag (html 100k) | 0.099 ms | 0.093 ms | -5.8% |
| on_selection_modified: caret in abbr (html small) | 0.053 ms | 0.056 ms | +5.8% |
| on_selection_modified: caret in abbr (html 10k) | 0.054 ms | 0.047 ms | -12.7% |
| on_selection_modified: move caret (html small) | 0.042 ms | 0.045 ms | +5.2% |
| on_selection_modified: move caret (html 10k) | 0.044 ms | 0.042 ms | -3.4% |
| on_selection_modified: move caret (html 100k) | 0.042 ms | 0.043 ms | +4.0% |
| on_selection_modified: move caret (python 10k) | 0.045 ms | 0.041 ms | -7.7% |
| on_activated (html small) | 0.054 ms | 0.053 ms | -1.2% |
| on_activated (html 10k) | 0.065 ms | 0.055 ms | -14.8% |
| on_query_completions: after ul>li (html small) | 2.204 ms | 0.610 ms | -72.3% |
| on_query_completions: after ul>li (html 10k) | 87.872 ms | 10.871 ms | -87.6% |
| on_query_completions: after ul>li (html 100k) | 882.914 ms | 110.139 ms | -87.5% |
| on_query_context: Tab key contexts (html small) | 2.056 ms | 0.581 ms | -71.7% |
| on_query_context: Tab key contexts (html 10k) | 87.969 ms | 10.719 ms | -87.8% |
| on_query_context: Tab key contexts (html 100k) | 881.914 ms | 110.742 ms | -87.4% |
| tag preview on: caret in close tag (html small) | 1.470 ms | 1.477 ms | +0.5% |
| tag preview on: caret in close tag (html 10k) | 68.493 ms | 68.835 ms | +0.5% |
| tag preview on: caret in close tag (html 100k) | 695.718 ms | 696.986 ms | +0.2% |
| tag preview on: caret in text (html small) | 1.435 ms | 0.092 ms | -93.6% |
| tag preview on: caret in text (html 10k) | 69.140 ms | 0.092 ms | -99.9% |
| tag preview on: caret in text (html 100k) | 697.755 ms | 0.089 ms | -100.0% |
| cmd emmet_expand_abbreviation p10 (css 10k) | 15.294 ms | 3.140 ms | -79.5% |
| cmd emmet_expand_abbreviation ul>li*3 (html small) | 1.192 ms | 0.817 ms | -31.4% |
| cmd emmet_expand_abbreviation ul>li*3 (html 10k) | 33.088 ms | 14.284 ms | -56.8% |
| cmd emmet_expand_abbreviation ul>li*3 (html 100k) | 340.203 ms | 141.733 ms | -58.3% |
| cmd emmet_balance outward (html small) | 2.816 ms | 2.834 ms | +0.6% |
| cmd emmet_balance outward (html 10k) | 138.113 ms | 139.164 ms | +0.8% |
| cmd emmet_balance outward (html 100k) | 1398.194 ms | 1399.364 ms | +0.1% |
| cmd emmet_go_to_tag_pair (html small) | 1.614 ms | 1.695 ms | +5.0% |
| cmd emmet_go_to_tag_pair (html 10k) | 68.781 ms | 69.837 ms | +1.5% |
| cmd emmet_go_to_tag_pair (html 100k) | 698.569 ms | 703.345 ms | +0.7% |
| cmd emmet_rename_tag (html small) | 1.619 ms | 1.715 ms | +5.9% |
| cmd emmet_rename_tag (html 10k) | 68.713 ms | 69.604 ms | +1.3% |
| reference: 1x native move by characters (html 10k) | 0.190 ms | 0.173 ms | -9.0% |

## What changed

- **Abbreviation context in HTML** (`context.get_html_context`): it walks every
  tag-name region from `find_by_selector()` and used to call `view.substr()` two or
  three times per tag, i.e. ~30,000 IPC round trips on a 10k-line page. It now reads
  the text once and slices it. This runs on the first keystroke of every abbreviation,
  on every Tab press in HTML (the `emmet_multicursor_tab_expand` key context), on
  `auto_complete` and on Expand Abbreviation: all **-72% to -88%**. On a
  100k-line page a keystroke that starts an abbreviation went from 0.89 s to 0.11 s.
  What is left is mostly `find_by_selector()` itself (native).
- **Abbreviation context in CSS** (`context.get_matching_section`): trimmed the
  leading whitespace of *every* selector and property list (one `substr()` per
  character) to find the one containing the caret. It now skips regions that cannot
  contain the caret first: **-89%** for typing, -80% for Expand Abbreviation.
- **Tag preview** (`go_to_tag_pair`, off by default): parsed the whole document on
  every caret move to find out whether the caret is in a closing tag. A cheap text
  check (is there a `</` right before the caret with no `>` in between?) now rules
  out all other positions first: **0.09 ms instead of 70 ms (10k) / 700 ms (100k)**.
  The check is a necessary condition; the unit tests compare it with the full match
  at every position of a sample document.
- `known_tags` is a frozenset (lookup per candidate check); no measurable change.

## What was measured and left alone

- **Balance, Go to Tag Pair, Rename Tag and tag preview in a closing tag** parse the
  whole document with the vendored py-emmet matcher (0.07 s at 10k lines, 0.7-1.4 s
  at 100k). A faster version would need a different parser or caching parse results
  in py-emmet, and the vendored code is not edited by hand. Commands run once per key
  press, so this was not changed.
- **Unrelated syntaxes**: in a 10k-line Python file Emmet costs 0.09 ms per keystroke
  and 0.04 ms per caret move (a few `match_selector()` calls), so a
  `ViewEventListener.is_applicable` split was not worth it. It would also be wrong
  for mixed files: Emmet decides per position (PHP, Markdown, embedded CSS), which
  `is_applicable(settings)` cannot see.
- **Typing inside an abbreviation, caret moves, `on_activated`**: already 0.04-0.17 ms,
  independent of file size. Differences in those rows are noise (compare the
  `reference` row).
- **Plugin load** (fresh import of main.py, lib/ and the vendored core): ~5.8 ms, unchanged.
- **Memory**: Emmet keeps no indexes, only one tracker per view, so there was nothing
  to measure.

## After hardening

The hardening commit added setting type checks on the hot paths. A second
back-to-back pair (upstream vs. the final code, 10k-line fixtures):

| Benchmark | Before | After | Change |
|---|---:|---:|---:|
| cmd emmet_expand_abbreviation ul>li*3 (html 10k) | 33.503 ms | 14.184 ms | -57.7% |
| on_query_completions: after ul>li (html 10k) | 87.686 ms | 11.642 ms | -86.7% |
| load: Emmet.main | 5.689 ms | 6.081 ms | +6.9% |
| on_selection_modified: move caret (html 10k) | 0.047 ms | 0.051 ms | +8.6% |
| on_selection_modified: move caret (python 10k) | 0.051 ms | 0.056 ms | +9.8% |
| reference: 1x native move by characters (html 10k) | 0.126 ms | 0.138 ms | +9.3% |
| on_query_context: Tab key contexts (html 10k) | 87.731 ms | 11.689 ms | -86.7% |
| tag preview on: caret in text (html 10k) | 68.718 ms | 0.105 ms | -99.8% |
| on_modified: type 1st abbr char (html 10k) | 88.555 ms | 11.011 ms | -87.6% |
| on_modified: type 1st abbr char (css 10k) | 30.134 ms | 3.037 ms | -89.9% |
| on_modified: type 1st abbr char (python 10k) | 0.092 ms | 0.098 ms | +6.1% |
| on_modified: type 2nd abbr char (html 10k) | 0.147 ms | 0.175 ms | +18.9% |

The big wins hold. The +6% to +19% rows are 5-28 µs per event; the native
`reference` row moved +9% in the same pair, so most of that is session noise.

## Protocol

Each row is the median of 20 timed runs after 3 warm-ups with GC paused
(`harness.py`). No single Sublime call runs longer than ~40 s (the 100k-line
balance row), so the editor is never blocked for long. Profiles were taken with
cProfile inside the plugin host at 10k lines.
