# Changelog

## [Unreleased] (fork branch `custom`)

Changes in this fork compared with upstream
[emmetio/sublime-text-plugin](https://github.com/emmetio/sublime-text-plugin) v2.4.5.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The upstream
history follows below.

Command names, arguments, key bindings, palette and menu entries and settings keys
are unchanged, except that the telemetry settings were removed (see Removed).

### Added
- The py-emmet core (1.3.1, latest on PyPI and GitHub) is vendored in `emmet/`
  (`tools/vendor_emmet.sh` re-creates it from the PyPI wheel and checks its SHA-256).
  Upstream installs it only when building the `.sublime-package`, so a git checkout
  failed to load (`No module named 'Emmet.emmet'`).
- `.python-version` `3.14`: runs on Sublime Text 4's Python 3.14 plugin host.
- UnitTesting suite in `tests/` (185 tests, 94% line coverage of `main.py` and `lib/`).
- Benchmarks in `tests/benchmarks/`, results in `PERFORMANCE.md`.
- `pyproject.toml` (ruff lint/format, pyright), `.coveragerc`, a UnitTesting type stub
  in `typings/`, and a GitHub Actions workflow running ruff, pyright and the tests.
- Settings with a wrong type (e.g. a string for `tag_preview_size_limit`, a non-list
  `known_snippets_only`, a non-dict `config`) are ignored with one console message
  instead of raising on every keystroke.

### Changed
- Starting an abbreviation, the Tab key and completions in HTML are 72-88% faster
  (one text read instead of one IPC call per tag); in CSS 89% faster; tag preview no
  longer parses the whole document on every caret move. See `PERFORMANCE.md`.
- Code modernized for Python 3.14: type hints, f-strings, no ST3 version checks,
  specific exceptions; dead code and `.pylintrc` removed.
- Convert data:URL reports failures (missing file, unsaved view, too large, unreadable)
  in the status bar, and reads at most `max_data_url` + 1 bytes of a remote image.

### Removed
- Telemetry. It posted usage events to Google Universal Analytics, which Google has
  shut down, and on a fresh install it sent events before asking for consent. The
  first-run consent dialog is gone, and the `telemetry` and `uid` settings are no
  longer read.

### Fixed
- **Wrap with Abbreviation** run with a `wrap_abbreviation` argument (key binding or
  another plugin) raised `AttributeError`, or wrapped the regions of an earlier,
  cancelled palette run. Two carets in the same tag raised `TypeError`.
- **Convert data:URL** in HTML always raised `AttributeError` (it called a missing
  `emmet.tag()`). It encoded images with the URL-safe base64 alphabet, which browsers
  reject in `data:` URLs; it now writes standard base64 (both are still read).
  Converting back to a file overwrote an existing file without asking, crashed in an
  unsaved view and silently dropped invalid base64 characters.
- **Update Image Size** ignored `@2x`-style suffixes (only `@1.5x` matched), and a
  truncated JPEG/SVG header raised instead of reporting "unable to determine size".
- Tag preview raised `AttributeError` on a valueless `class`/`id` attribute.
- Self-closing tags without attributes produced a broken abbreviation context.

## 2.4.1

* Automatically remove empty `for` attribute in `<label>` element if it contains nested `<input>` or `<textarea>` element.

## 2.4.0

* Emmet just got better for JSX and Vue devs: use cleaner and shorter
  abbreviations to work with CSS modules and CSS-in-JS. For example, you can
  write `..my-class` abbreviation to get `<div styleName={styles['my-class']}>`.
  Read more in py-emmet v1.2.0 CHANGELOG: https://github.com/emmetio/py-emmet/blob/master/CHANGELOG.md#120-2023-01-19
  Feature discussion: https://github.com/emmetio/emmet/issues/589
* Fixed missing semicolon inside `@media` rule (#173)
* Support abbreviations inside `@supports (...) {}` query
* Removed extra spaces in CSS snippet output with parentheses in value (https://github.com/emmetio/emmet/issues/647).
* Added `script:module` HTML snippet.
* Added `g` (`gap`) CSS snippet, replaced `dc` with `display: contents` instead of invalid `display: compact`.

## 2.3.0

* Stability improvements in main Emmet package

## 2.2.0

* Expand abbreviations from multiple cursors.

## 2.1.0

* Introduce `known_snippets_only` option, which is enabled by default for HTML syntaxes. It allows to expand a single-word abbreviation only if it’s a known HTML tag, Emmet snippet or common component pattern.
* Improved unmatched CSS abbreviations handling: https://github.com/emmetio/sublime-text-plugin/issues/45


## 2.0.0

Final release of Emmet.

## v0.2.4

* Support TSX syntax.
* Minor tweaks and improvements in abbreviation activation scopes.

## v0.2.1

* Improved typing experience: detect unwanted abbreviations in some common cases.
* Improved error snippet for invalid abbreviation
* Disabled Emmet commenting by default

## v0.2.0

* Complete rewrite of abbreviation tracker (detect abbreviation as-you-type). It should be less annoying: display expanded preview only if abbreviation contains more than one element.
* Explicit Abbreviation Mode: run `Emmet: Enter Abbreviation Mode` to enter explicit abbreviation typing mode. Run this action in *any* syntax to enter abbreviation with real-time preview and validation. Hit <kbd>Enter</kbd> or <kbd>Tab</kbd> to expand abbreviation, <kbd>Esc</kbd> to clear entered abbreviation and exit mode.
* Moved preferences from `Preferences.sublime-settings` (global to Sublime Text) into `Emmet.sublime-settings` file.
* Syntax highlighting of HTML abbreviation preview.
