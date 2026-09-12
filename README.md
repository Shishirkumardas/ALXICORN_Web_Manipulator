# ALXICORN Web Manipulator

Windows desktop automation that **sees** two live websites and **acts** on them — no CSS selectors, no DOM, no browser extension.

It takes screenshots, finds PNG templates with OpenCV, then clicks and types with PyAutoGUI.

| Task | Site | Action |
| --- | --- | --- |
| 1 | [mediawiki.org/wiki/MediaWiki](https://www.mediawiki.org/wiki/MediaWiki) | Find the Appearance **Width** radios and click **Wide** |
| 2 | [propertychecker.co.uk](https://propertychecker.co.uk/) | Find the postcode field, type `CW6 0AR`, click **Check Now** |

Built as an Alxicorn technical assessment. The script is intentionally vision-based so it still works when the page markup changes, as long as the UI still *looks* like the reference images.

---

## How it works

```
reference PNG  ──►  OpenCV matchTemplate (many scales)
                         │
                         ▼
              screen coordinates of the widget
                         │
                         ▼
              PyAutoGUI click / type
```

1. Launch (or focus) a real browser window.
2. Force it to the foreground and maximize it. Windows otherwise blocks focus steals from a Python process.
3. Grab a full-desktop screenshot (all monitors, DPI-aware).
4. Slide each reference image across the screenshot at ~20 scales (50%–200%) so 125% / 150% / 200% display scaling still matches.
5. Click a target *inside* the matched box:
   - MediaWiki: Hough-circle detection of the radio stack; the **last** circle is Wide.
   - Property Checker: brightest white rectangle is the input; navy blob below the crop is **Check Now**.

Annotated screenshots are written to `debug_output/` so you can see what it matched.

---

## Requirements

- Windows 10 / 11
- Python 3.10+
- Microsoft Edge (preferred), Google Chrome, or Firefox
- The two reference PNGs in `references/` (they ship with this repo; Google Drive is only a fallback download)

## Setup

```powershell
cd ALXICORN_Web_Manipulator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Move the mouse to the **top-left corner** of the screen to abort (PyAutoGUI failsafe).

```powershell
python main.py
```

Expected console ending:

```
ALXICORN WEB MANIPULATOR FINISHED
MediaWiki:        PASS
Property Checker: PASS
```

Leave the machine alone for about 30–60 seconds. The script drives the mouse and keyboard.

---

## Project layout

```
ALXICORN_Web_Manipulator/
├── main.py                 # entire automation
├── requirements.txt
├── README.md
├── CODE_EXPLAINER.md       # line-by-line walkthrough of main.py
├── references/
│   ├── ref-1.png           # Width > Standard / Wide radios
│   └── ref-2.png           # Check Property Prices + postcode field
└── debug_output/           # created at runtime (gitignored)
```

## Configuration (top of `main.py`)

| Constant | Meaning |
| --- | --- |
| `MEDIAWIKI_URL` | Official MediaWiki site (not the Wikipedia article) |
| `PROPERTY_CHECKER_URL` | Property Checker homepage |
| `POSTCODE` | Value typed into the form (`CW6 0AR`) |
| `MATCH_THRESHOLD` | Minimum OpenCV confidence (default `0.62`) |
| `SCALES` | Template resize factors for DPI / zoom |
| `PAGE_LOAD_WAIT` | Seconds to wait after the browser window appears |

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| `Reference image was not found` | Check `debug_output/failed_*.png`. Make sure the browser is visible and not covered. |
| Clicks land in the wrong window | Close leftover Settings / Explorer / editor windows, then rerun. |
| MediaWiki window not found | The script looks for a browser title like `MediaWiki - Personal` and ignores Wikipedia, Grok, and still-loading `mediawiki.org/wiki` titles. |
| Width radios not found | Another window (editor/TUI) may be covering the right-hand Appearance panel. The script minimizes `grok` windows during matching. |
| Postcode not typed | The browser must keep keyboard focus; don't click elsewhere mid-run. |
| Confidence around 0.3 | The wrong window was captured. Look at the printed `Browser window:` title. |

## License

Personal / assessment project. Use and modify freely.
