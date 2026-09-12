# Line-by-line explainer — `main.py`

This file walks through `main.py` in order. Line numbers match the current source.

---

## Lines 1–13 — Module docstring

| Line | Code | What it does |
| --- | --- | --- |
| 1–13 | `""" ... """` | Package-level description shown by `help()` and GitHub. States the two tasks (MediaWiki Wide radio, Property Checker postcode) and that the script is vision-only: screenshots + OpenCV + PyAutoGUI, never the DOM. |

---

## Lines 15–27 — Imports

| Line | Code | What it does |
| --- | --- | --- |
| 15 | `import os` | Check whether Edge / Chrome / Firefox exist on disk (`os.path.exists`). |
| 16 | `import sys` | `sys.exit(main())` so the process exit code is 0 on PASS and 1 on FAIL. |
| 17 | `import time` | Sleeps between page load, retries, and clicks. |
| 18 | `import ctypes` | Call Win32 APIs (`user32` / `kernel32`) that Python cannot reach otherwise. |
| 19 | `import subprocess` | `Popen` launches a new browser process without blocking the script. |
| 20 | `import webbrowser` | Fallback if no known browser EXE is installed; also used to open a URL in an existing window. |
| 21 | `from pathlib import Path` | Join `references/` and `debug_output/` in a cross-path-safe way, including Unicode filenames. |
| 22 | *(blank)* | Separates stdlib from third-party imports. |
| 23 | `import cv2` | OpenCV: decode PNGs, `matchTemplate`, Hough circles, colour masks. |
| 24 | `import numpy as np` | Image arrays, NaN checks, morphology kernels. |
| 25 | `import pyautogui` | Move the real mouse, click, type, hotkeys (`ctrl+a`, `ctrl+home`). |
| 26 | `import requests` | HTTP GET to Google Drive if a reference PNG is missing locally. |
| 27 | `from PIL import ImageGrab` | Screenshot every monitor (`all_screens=True`). |

---

## Lines 30–67 — Configuration

| Line | Code | What it does |
| --- | --- | --- |
| 30–32 | section banner | Visual divider in the source. |
| 34 | `PROJECT_NAME = "ALXICORN_Web_Manipulator"` | Canonical project name. |
| 36–37 | comments | Why mediawiki.org (Vector 2022 Appearance panel) instead of Wikipedia. |
| 38 | `MEDIAWIKI_URL = "https://www.mediawiki.org/wiki/MediaWiki"` | Task 1 URL — official MediaWiki wiki, not `en.wikipedia.org`. |
| 39 | `PROPERTY_CHECKER_URL = "https://propertychecker.co.uk/"` | Task 2 URL. |
| 40 | `POSTCODE = "CW6 0AR"` | Text typed into the postcode field. |
| 42–43 | `REF1_FILE_ID` / `REF2_FILE_ID` | Google Drive file IDs. Used only when `references/ref-1.png` or `ref-2.png` are absent. |
| 45 | `HERE = Path(__file__).resolve().parent` | Directory that contains `main.py`, no matter where you launch it from. |
| 46 | `REFERENCES_DIR = HERE / "references"` | Folder of template PNGs. |
| 47 | `DEBUG_DIR = HERE / "debug_output"` | Folder for match overlays and failure screenshots. |
| 49 | `REF1_PATH = ... / "ref-1.png"` | Template for the Width radios. |
| 50 | `REF2_PATH = ... / "ref-2.png"` | Template for the postcode card. |
| 52 | `MATCH_THRESHOLD = 0.62` | `TM_CCOEFF_NORMED` scores below this are treated as “not found”. |
| 53 | `SEARCH_TIMEOUT = 25` | Seconds to keep retrying a match after the page opens. |
| 54 | `RETRY_INTERVAL = 0.8` | Pause between match attempts. |
| 55 | `PAGE_LOAD_WAIT = 5` | Seconds to wait after the browser window is focused. |
| 57–63 | `SCALES = (...)` | Resize factors for the template. 1.25 covers 125% DPI (common on this machine); 2.00 covers 200%. Tiny or oversized scales are skipped later if they don't fit the screenshot. |
| 65–67 | `EDGE` / `CHROME` / `FIREFOX` | Default Windows install paths. First existing EXE wins. |

---

## Lines 70–84 — Win32 constants

| Line | Code | What it does |
| --- | --- | --- |
| 73–74 | `user32` / `kernel32` | Loaded once. `user32` owns windows; `kernel32` owns threads. |
| 76 | `SW_RESTORE = 9` | Restore a minimized window before maximizing. |
| 77 | `SW_MAXIMIZE = 3` | Maximize so the UI is as large and consistent as possible. |
| 78 | `HWND_TOPMOST = -1` | Z-order: sit above every other window. |
| 79 | `HWND_NOTOPMOST = -2` | Z-order: normal (used to release topmost after the click). |
| 80–82 | `SWP_NOMOVE` / `SWP_NOSIZE` / `SWP_SHOWWINDOW` | `SetWindowPos` flags: change Z-order only, then show. |

---

## Lines 86–95 — `make_dpi_aware`

| Line | Code | What it does |
| --- | --- | --- |
| 86–87 | `def make_dpi_aware():` + docstring | Per-monitor DPI awareness so screenshot pixels line up with cursor pixels. Without this, a click aimed at (100, 100) can land at (125, 125) on a 125% display. |
| 88–90 | `SetProcessDpiAwareness(2)` | Per-monitor v2 DPI. Wrapped in `try` because older Windows has no `shcore`. |
| 91–95 | `SetProcessDPIAware()` fallback | System-DPI awareness on older Windows. Failures are ignored — matching still runs, just less accurately. |

---

## Lines 98–151 — Window focus helpers

### `maximize_window` (98–101)

| Line | What it does |
| --- | --- |
| 99 | Cast the handle to `int` (pygetwindow sometimes yields a numpy-like type). |
| 100 | Restore if minimized. Maximizing a minimized window is unreliable. |
| 101 | Maximize. |

### `force_foreground` (104–140)

Windows blocks a background process from stealing focus. This function cheats legally: attach to the current foreground thread, then set topmost.

| Line | What it does |
| --- | --- |
| 104–106 | Signature + docstring. `stay_topmost=True` keeps the browser above this editor during matching. |
| 107 | Normalize hwnd. |
| 109–110 | Who currently has focus, and that window's thread. |
| 111 | This Python process's thread. |
| 112–114 | `AttachThreadInput` lets `SetForegroundWindow` succeed. |
| 116–121 | `SetWindowPos(..., HWND_TOPMOST)` — float above everything. |
| 122–123 | Bring to top + request foreground. |
| 125–132 | If `stay_topmost` is false, drop back to normal Z-order. |
| 134–135 | Detach the threads so we don't leak the attach. |
| 137–140 | Optional COM `AppActivate` via `pywin32`. Extra insurance; ignored if pywin32 is missing. |

### `release_topmost`

No-op when `hwnd` is missing. Otherwise `SetWindowPos` with `HWND_NOTOPMOST` so the browser is no longer glued above other apps.

### `minimize_interfering_windows`

Finds windows whose titles contain `grok` (this editor) and minimizes them with `SW_MINIMIZE` (6), skipping the browser `hwnd`. Template matching needs an unobstructed screenshot of the page; a floating TUI covering the Appearance panel makes MediaWiki fail.

### `restore_windows`

Restores every HWND that was minimized, so the editor comes back after the task.

### `_window_hwnd_and_title` (154–157)

| Line | What it does |
| --- | --- |
| 155 | pygetwindow stores the HWND as `_hWnd` or `_hwnd` depending on version. |
| 156–157 | Title string (empty if the window is title-less) and return both. |

---

## Lines 160–248 — Finding and opening a browser

### `find_window` (160–184)

| Line | What it does |
| --- | --- |
| 161–164 | Import `pygetwindow` lazily. If it isn't installed, return `None` and the script still screenshots whatever is visible. |
| 166–167 | Lowercase needles and exclude list for case-insensitive matching. |
| 168–169 | Track the best `(hwnd, title)` and its rank score. |
| 170–173 | Skip windows with no handle or empty title. |
| 175–176 | Skip titles that contain an exclude string (`Wikipedia`, `grok`). That stops this editor (whose title contains `mediawiki.org`) and Wikipedia tabs from being treated as the official MediaWiki site. |
| 177–183 | First matching needle wins for that window; earlier needles in the list score higher. Keep the highest-scoring window across the desktop. |
| 184 | Return that pair, or `None`. |

### `wait_for_window` (187–194)

| Line | What it does |
| --- | --- |
| 188 | Deadline = now + timeout (default 20 s). |
| 189–192 | Poll every 0.3 s until a matching window appears (browser still launching). |
| 194 | Give up with `None`. |

### `launch_browser` (197–207)

| Line | What it does |
| --- | --- |
| 198–200 | Edge: `--new-window --start-maximized URL`. New window, not a tab in a 14-tab session. |
| 201–203 | Chrome, same flags. |
| 204–206 | Firefox: `-new-window`. |
| 207 | Last resort: OS default handler. |

### `open_site` (210–248)

| Line | What it does |
| --- | --- |
| 210–217 | Parameters: URL, title needles, load wait, `always_open` (navigate even if a window already matches), `exclude_substrings`, `force_new` (always launch, never reuse). |
| 218 | Log the URL. |
| 219–221 | If `force_new`, skip the existing-window search (MediaWiki always wants a fresh window). |
| 222–226 | Nothing found → launch, then wait up to 25 s. |
| 227–232 | `always_open`: `webbrowser.open` (usually a new tab in the existing browser), wait 2 s, re-query. |
| 233–236 | Still nothing: warn and screenshot the current desktop anyway. |
| 238–241 | Print the title, maximize, force foreground. |
| 242 | Wait for the page to paint. |
| 243 | Focus again (some pages steal it with a banner). |
| 244 | `Esc` dismisses cookie / appearance popovers. |
| 245–246 | `Ctrl+Home` scrolls to the top so the Width panel is on-screen — but only if we still own focus, so we don't scroll some other app. |
| 247–248 | Tiny settle delay; return hwnd for later focusing. |

---

## Lines 251–293 — Image I/O

### `load_bgr` (255–271)

| Line | What it does |
| --- | --- |
| 256–258 | Read bytes then `cv2.imdecode`. This works with Unicode paths (`E:\...`) where `cv2.imread` can fail on Windows. |
| 259–260 | Invalid file → `None`. |
| 262–269 | If the PNG has an alpha channel, composite it onto white. Transparent screenshot chrome would otherwise match as black and wreck the template. |
| 271 | Crop the dark rounded “window screenshot” border that is not part of the site. |

### `crop_dark_frame` (274–283)

| Line | What it does |
| --- | --- |
| 275–276 | Docstring + grayscale. |
| 277 | Pixels brighter than 40 are “content”. |
| 278–279 | No bright pixels → return original. |
| 280–282 | Bounding box of content, inset 2 px, slice. |
| 283 | If the crop emptied the image, keep the original. |

### `take_screenshot` (286–288)

| Line | What it does |
| --- | --- |
| 287 | PIL grab of **all** monitors (the Width panel may sit on a second display). |
| 288 | RGB → BGR because OpenCV is BGR. |

### `save_debug` (291–293)

| Line | What it does |
| --- | --- |
| 292 | Create `debug_output/` if needed. |
| 293 | Write the PNG. Used for `match_*.png`, `after_*.png`, `failed_*.png`. |

---

## Lines 296–406 — Template matching

### `find_reference_multiscale` (300–375)

This is the core locator.

| Line | What it does |
| --- | --- |
| 300 | `reference_path`, confidence `threshold`, optional pre-grabbed `screen`. |
| 301–304 | Load template; abort if missing. |
| 306–307 | Screenshot now unless the caller already passed one. |
| 309–310 | Both images to grayscale. Colour is irrelevant for this UI and slower. |
| 311 | Remember the **full** template size so the returned box still covers the radios after the “no-radios” crop. |
| 313–318 | Two variants: (1) the whole PNG; (2) drop the left ~24% (the radio column) so matching still works after Standard/Wide has already changed. `left_offset` is added back so the box origin is the full widget, not the cropped template. |
| 320–322 | For each variant, for each scale in `SCALES`. |
| 324–329 | Skip scales that shrink below 12 px or grow larger than the screenshot. |
| 331–335 | Downscale with `INTER_AREA`, upscale with `INTER_LINEAR`. |
| 336–337 | Normalized correlation. `minMaxLoc` gives the best peak and its top-left. |
| 338–339 | Skip NaN peaks (can happen on degenerate templates). |
| 340–343 | Convert peak to a **full-template** rectangle, compensating for the left crop and the scale. |
| 344–356 | Keep the highest confidence. If we already have ≥ 0.92, stop this variant's scale loop (good enough). |
| 357–358 | If that 0.92 match exists, skip the second variant entirely. |
| 360–361 | No peak at all → `None`. |
| 363–368 | Log confidence, scale, variant, pixel position. |
| 370–372 | Below `MATCH_THRESHOLD` → treat as not found. |
| 374–375 | Log success and return the match dict (`x, y, width, height, scale, confidence, screen, variant`). |

### `wait_for_reference` (378–389)

| Line | What it does |
| --- | --- |
| 379–381 | Start timer; `last` holds the most recent failed/successful attempt. |
| 382–387 | Until timeout: refocus the browser, try to match, return on success, else sleep `RETRY_INTERVAL`. |
| 389 | Return `last` (usually `None` after a string of failures). |

### `annotate_match` (392–406)

| Line | What it does |
| --- | --- |
| 393–394 | Copy the screenshot; unpack the box. |
| 395 | Green rectangle around the match. |
| 396–405 | Label `ref-1.png 0.85` above the box. |
| 406 | Save `debug_output/match_ref-1.png` (stem of the filename). |

---

## Lines 409–542 — Click targets inside a match

### `radio_offsets` (413–436)

Finds the vertical stack of circular radio buttons.

| Line | What it does |
| --- | --- |
| 414–416 | Grayscale + median blur (Hough is noisy on sharp UI edges). |
| 417 | `min_dim` scales the circle-detector to the crop size. |
| 418–427 | `HoughCircles`: gradient method, min distance between centres, radius band that fits these radios. |
| 428–429 | No circles → empty list (caller will use a percentage fallback). |
| 430 | Sort by Y so the stack is top→bottom (Standard then Wide). |
| 431–432 | Need at least two radios. |
| 433–435 | If X spread is huge, these are not a vertical stack — reject. |
| 436 | Return `(x, y)` centres in **local** crop coordinates. |

### `white_input_offset` (439–458)

Finds the pale postcode field.

| Line | What it does |
| --- | --- |
| 440–442 | HSV mask of near-white, low-saturation pixels. |
| 443 | Close small gaps so the field is one blob. |
| 444–447 | Contours; keep the largest that looks like a wide input (not the heading). |
| 448 | Ignore the top 40% of the crop (that's the “Check Property Prices” title). |
| 449–451 | Height 28–120 px, width ≥ 120 px. |
| 452–455 | Click a third of the way in from the left, vertically centred — inside the typing area, not the rounded corner. |
| 456–458 | Fallback percentages if no contour qualifies. |

### `foreground_is` (461–462)

True when `hwnd` is the OS foreground window. Used to avoid sending `Ctrl+Home` / keystrokes to the editor.

### `click_xy` (465–471)

| Line | What it does |
| --- | --- |
| 466–467 | Refocus first. |
| 468–471 | Move (0.2 s), pause, click, pause. Instant teleports miss hover/focus styles. |

### `grab_keyboard` (474–480)

Refocus and warn if Windows still refused. Typing into the wrong app is worse than a warning.

### `navy_button_below` (483–505)

The **Check Now** button sits *under* the reference crop, so it is not inside the match box.

| Line | What it does |
| --- | --- |
| 485–488 | Strip of pixels immediately below the match, left half (the button is left-aligned). |
| 489–491 | Empty strip → `None` (caller presses Enter instead). |
| 492–493 | HSV mask of dark blue (navy). |
| 494–504 | Largest contour that is button-shaped (w ≥ 70, h 24–80). Return its centre in **screen** coordinates. |

### `click_wide_radio` (508–524)

| Line | What it does |
| --- | --- |
| 509–512 | Slice the matched region out of the screenshot. |
| 513–515 | If Hough found radios, take the **last** (bottom) one — Wide. |
| 516–518 | Else click ~16% from the left, ~78% down — empirically where Wide sits in the reference. |
| 519–524 | Convert local → screen, log, focus, click. Always returns `True` (the click was issued; we don't OCR the result). |

### `click_postcode_field` (527–541)

| Line | What it does |
| --- | --- |
| 528–534 | Same crop; locate the white field; convert to screen coords. |
| 535–540 | Focus, click, short pause, click again. The second click fights sites that steal focus on the first click. |

---

## Lines 545–586 — Reference image download

### `download_from_google_drive` (548–571)

| Line | What it does |
| --- | --- |
| 549–550 | Ensure `references/` exists. |
| 552–554 | Already on disk → skip the network. The repo ships the PNGs, so this is a fallback. |
| 556–557 | Google Drive “direct download” URL. |
| 558–571 | GET, write bytes, validate with `load_bgr`. Any HTTP / decode error prints and returns `False`. |

### `prepare_reference_images` (574–586)

Prints a banner, downloads ref-1 then ref-2, returns `False` if either fails so `main` can abort with exit code 1.

---

## Lines 589–681 — The two tasks

### `mediawiki_task` (593–627)

| Line | What it does |
| --- | --- |
| 594–597 | Banner. |
| 599–610 | `open_site` on mediawiki.org. Title needles match Edge/Chrome/Firefox window titles (`MediaWiki - Personal`, etc.). Excludes Wikipedia, Grok, and loading titles that still contain `mediawiki.org/wiki` or `https://` so we don't match a blank tab. `force_new=True` always launches a dedicated window. Wait is at least 7 seconds so Vector 2022 can paint the Appearance panel. |
| 612–618 | Wait for ref-1. On failure, save `failed_mediawiki.png` and return `False`. |
| 620–621 | Draw the overlay; click Wide. |
| 622–623 | Let the skin apply; save `after_mediawiki.png` (Wide should be selected). |
| 624–627 | Release topmost; print SUCCESS. |

### `property_checker_task` (634–681)

| Line | What it does |
| --- | --- |
| 635–638 | Banner. |
| 640–645 | Open propertychecker.co.uk. `always_open=True` navigates even if a Property Checker window already exists. |
| 647–653 | Wait for ref-2. On failure, save `failed_property.png`. |
| 655–658 | Overlay; click the input; refocus for typing. |
| 660–664 | Select-all, backspace, type `CW6 0AR` with a 50 ms gap per character (too fast and the field drops keys). |
| 665 | Save `typed_property.png`. |
| 667–673 | Click the navy **Check Now** if found, else press Enter. |
| 675–681 | Wait for results, save `after_property.png`, release topmost, SUCCESS. |

---

## Lines 684–719 — `main` and entry point

| Line | What it does |
| --- | --- |
| 686 | `make_dpi_aware()` first, before any screenshot or click. |
| 687 | Failsafe: yank the mouse to the top-left corner to abort. |
| 688 | 50 ms pause after every PyAutoGUI call so the OS can keep up. |
| 689 | Ensure `debug_output/` exists even if both tasks fail immediately. |
| 691–694 | Banner. |
| 696–698 | Abort with exit code 1 if the reference PNGs cannot be loaded or downloaded. |
| 700–703 | Human-readable pause so you can see the message before the browser jumps in front. |
| 705 | Task 1. |
| 706 | Two seconds between tasks so MediaWiki can finish painting before Property Checker opens. |
| 707 | Task 2. |
| 709–715 | Summary line per task (`PASS` / `FAIL`). |
| 715 | Exit code 0 only if **both** tasks returned True. |
| 718–719 | Standard Python entry: running `python main.py` calls `main()` and uses its return value as the process exit code. Importing `main` as a module does not auto-run. |

---

## Data that is *not* in `main.py`

| Path | Role |
| --- | --- |
| `references/ref-1.png` | Crop of Appearance → Width (Standard / Wide). |
| `references/ref-2.png` | Crop of “Check Property Prices” + the empty postcode field. |
| `debug_output/` | Created at runtime. Gitignored. |
| `requirements.txt` | Third-party packages. |
| `.gitignore` | Keeps `__pycache__/` and `debug_output/` out of Git. |
