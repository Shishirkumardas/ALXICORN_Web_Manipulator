"""
ALXICORN Web Manipulator
========================
Desktop vision automation for two live websites:

1. MediaWiki  — open mediawiki.org, find the Appearance > Width radios,
                click Wide.
2. Property Checker — open propertychecker.co.uk, find the postcode field,
                type CW6 0AR, and submit.

The script never uses CSS selectors or the DOM. It screenshots the desktop,
matches PNG templates with OpenCV, then clicks/types with PyAutoGUI.
"""

import os
import sys
import time
import ctypes
import subprocess
import webbrowser
from pathlib import Path

import cv2
import numpy as np
import pyautogui
import requests
from PIL import ImageGrab


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_NAME = "ALXICORN_Web_Manipulator"

# Official MediaWiki site uses Vector 2022, which shows the
# Appearance > Width (Standard / Wide) radios from Reference 1.
MEDIAWIKI_URL = "https://www.mediawiki.org/wiki/MediaWiki"
PROPERTY_CHECKER_URL = "https://propertychecker.co.uk/"
POSTCODE = "CW6 0AR"

REF1_FILE_ID = "1Mf_AKkSxXDQYgvJfoU8bLKjLOt5JNi_Z"
REF2_FILE_ID = "1KYbENGuKC6b4D2hSY08-RTn4ZrFmCCB1"

HERE = Path(__file__).resolve().parent
REFERENCES_DIR = HERE / "references"
DEBUG_DIR = HERE / "debug_output"

REF1_PATH = REFERENCES_DIR / "ref-1.png"
REF2_PATH = REFERENCES_DIR / "ref-2.png"

MATCH_THRESHOLD = 0.62
SEARCH_TIMEOUT = 25
RETRY_INTERVAL = 0.8
PAGE_LOAD_WAIT = 5

# Include 1.25x (125% DPI, typical on this machine) and 2.0x (200%).
SCALES = (
    0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95,
    1.00, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35,
    1.40, 1.50, 1.60, 1.75, 2.00,
)

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FIREFOX = r"C:\Program Files\Mozilla Firefox\firefox.exe"


# ============================================================
# WINDOWS DPI + FOCUS
# ============================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SW_MAXIMIZE = 3
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


def make_dpi_aware():
    """Match screenshot pixels to cursor pixels on Windows."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def maximize_window(hwnd):
    hwnd = int(hwnd)
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.ShowWindow(hwnd, SW_MAXIMIZE)


def force_foreground(hwnd, stay_topmost=True):
    """Bring a window above this process (Windows blocks normal focus steals)."""
    hwnd = int(hwnd)

    foreground = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    current_thread = kernel32.GetCurrentThreadId()
    attached = False
    if foreground_thread and foreground_thread != current_thread:
        attached = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))

    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)

    if not stay_topmost:
        user32.SetWindowPos(
            hwnd,
            HWND_NOTOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )

    if attached:
        user32.AttachThreadInput(current_thread, foreground_thread, False)

    try:
        import win32com.client

        win32com.client.Dispatch("WScript.Shell").AppActivate(hwnd)
    except Exception:
        pass


def release_topmost(hwnd):
    if not hwnd:
        return
    user32.SetWindowPos(
        int(hwnd),
        HWND_NOTOPMOST,
        0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
    )


def minimize_interfering_windows(keep_hwnd=None, title_needles=("grok",)):
    """Get editor / TUI windows off the screenshot so template matching sees the page."""
    try:
        import pygetwindow as gw
    except ImportError:
        return []

    keep = int(keep_hwnd) if keep_hwnd else None
    minimized = []
    for window in gw.getAllWindows():
        hwnd, title = _window_hwnd_and_title(window)
        if not hwnd or not title:
            continue
        if keep is not None and int(hwnd) == keep:
            continue
        lower = title.lower()
        if not any(needle in lower for needle in title_needles):
            continue
        try:
            user32.ShowWindow(int(hwnd), 6)  # SW_MINIMIZE
            minimized.append(int(hwnd))
        except Exception:
            pass
    return minimized


def restore_windows(hwnds):
    for hwnd in hwnds or []:
        try:
            user32.ShowWindow(int(hwnd), SW_RESTORE)
        except Exception:
            pass


def _window_hwnd_and_title(window):
    hwnd = getattr(window, "_hWnd", None) or getattr(window, "_hwnd", None)
    title = window.title or ""
    return hwnd, title


def find_window(title_substrings, exclude_substrings=None):
    try:
        import pygetwindow as gw
    except ImportError:
        return None

    needles = [s.lower() for s in title_substrings]
    exclude = [s.lower() for s in (exclude_substrings or [])]
    best = None
    best_rank = -1
    for window in gw.getAllWindows():
        hwnd, title = _window_hwnd_and_title(window)
        if not hwnd or not title:
            continue
        lower = title.lower()
        if any(ex in lower for ex in exclude):
            continue
        for rank, needle in enumerate(needles):
            if needle in lower:
                score = len(needles) - rank
                if score > best_rank:
                    best = (hwnd, title)
                    best_rank = score
                break
    return best


def wait_for_window(title_substrings, timeout=20, exclude_substrings=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = find_window(title_substrings, exclude_substrings=exclude_substrings)
        if found:
            return found
        time.sleep(0.3)
    return None


def launch_browser(url):
    if os.path.exists(EDGE):
        subprocess.Popen([EDGE, "--new-window", "--start-maximized", url])
        return
    if os.path.exists(CHROME):
        subprocess.Popen([CHROME, "--new-window", "--start-maximized", url])
        return
    if os.path.exists(FIREFOX):
        subprocess.Popen([FIREFOX, "-new-window", url])
        return
    webbrowser.open(url)


def open_site(
    url,
    title_substrings,
    wait=PAGE_LOAD_WAIT,
    always_open=False,
    exclude_substrings=None,
    force_new=False,
):
    print(f"Opening {url}")
    existing = None if force_new else find_window(
        title_substrings, exclude_substrings=exclude_substrings
    )
    if existing is None:
        launch_browser(url)
        existing = wait_for_window(
            title_substrings, timeout=25, exclude_substrings=exclude_substrings
        )
    elif always_open:
        webbrowser.open(url)
        time.sleep(2)
        existing = find_window(
            title_substrings, exclude_substrings=exclude_substrings
        ) or existing
    if existing is None:
        print("WARNING: Browser window was not found by title. Matching the current screen anyway.")
        time.sleep(wait)
        return None

    hwnd, title = existing
    print(f"Browser window: {title}")
    maximize_window(hwnd)
    force_foreground(hwnd, stay_topmost=True)
    time.sleep(wait)
    force_foreground(hwnd, stay_topmost=True)
    pyautogui.press("esc")
    if foreground_is(hwnd):
        pyautogui.hotkey("ctrl", "home")
    time.sleep(0.4)
    return hwnd


# ============================================================
# IMAGES
# ============================================================

def load_bgr(path):
    path = Path(path)
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        return None

    if image.ndim == 3 and image.shape[2] == 4:
        bgr = image[:, :, :3]
        alpha = image[:, :, 3].astype(np.float32) / 255.0
        white = np.full_like(bgr, 255)
        image = (
            bgr.astype(np.float32) * alpha[..., None]
            + white.astype(np.float32) * (1.0 - alpha[..., None])
        ).astype(np.uint8)

    return crop_dark_frame(image)


def crop_dark_frame(image):
    """Strip the dark rounded screenshot border that is not part of the site."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    coords = cv2.findNonZero((gray > 40).astype(np.uint8))
    if coords is None:
        return image
    x, y, w, h = cv2.boundingRect(coords)
    inset = 2
    cropped = image[y + inset : y + h - inset, x + inset : x + w - inset]
    return cropped if cropped.size else image


def take_screenshot():
    shot = ImageGrab.grab(all_screens=True)
    return cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)


def save_debug(name, image):
    DEBUG_DIR.mkdir(exist_ok=True)
    cv2.imwrite(str(DEBUG_DIR / name), image)


# ============================================================
# TEMPLATE MATCHING
# ============================================================

def find_reference_multiscale(reference_path, threshold=MATCH_THRESHOLD, screen=None):
    reference = load_bgr(reference_path)
    if reference is None:
        print(f"Could not load reference: {reference_path}")
        return None

    if screen is None:
        screen = take_screenshot()

    screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    reference_gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    original_height, original_width = reference_gray.shape

    # Full template plus a crop that drops the left radio column so the
    # match still works after Standard / Wide selection changes.
    variants = [
        ("full", reference_gray, 0),
        ("no-radios", reference_gray[:, int(original_width * 0.24) :], int(original_width * 0.24)),
    ]

    best_match = None
    for variant_name, template, left_offset in variants:
        tpl_h, tpl_w = template.shape[:2]
        for scale in SCALES:
            width = int(tpl_w * scale)
            height = int(tpl_h * scale)
            if width < 12 or height < 12:
                continue
            if width >= screen_gray.shape[1] or height >= screen_gray.shape[0]:
                continue

            resized = cv2.resize(
                template,
                (width, height),
                interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR,
            )
            result = cv2.matchTemplate(screen_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, confidence, _, location = cv2.minMaxLoc(result)
            if np.isnan(confidence):
                continue
            x = int(location[0] - left_offset * scale)
            y = int(location[1])
            full_w = int(original_width * scale)
            full_h = int(original_height * scale)
            if best_match is None or confidence > best_match["confidence"]:
                best_match = {
                    "x": max(0, x),
                    "y": max(0, y),
                    "width": full_w,
                    "height": full_h,
                    "scale": float(scale),
                    "confidence": float(confidence),
                    "screen": screen,
                    "variant": variant_name,
                }
                if confidence >= 0.92:
                    break
        if best_match and best_match["confidence"] >= 0.92:
            break

    if best_match is None:
        return None

    print(
        f"Best confidence: {best_match['confidence']:.3f}  "
        f"scale: {best_match['scale']:.2f}  "
        f"variant: {best_match.get('variant', 'full')}  "
        f"at: ({best_match['x']}, {best_match['y']})"
    )

    if best_match["confidence"] < threshold:
        print("Reference image was not found with sufficient confidence.")
        return None

    print(f"Reference found at: ({best_match['x']}, {best_match['y']})")
    return best_match


def wait_for_reference(reference_path, timeout=SEARCH_TIMEOUT, hwnd=None):
    start = time.time()
    last = None
    while time.time() - start < timeout:
        if hwnd:
            force_foreground(hwnd, stay_topmost=True)
        last = find_reference_multiscale(reference_path)
        if last is not None:
            return last
        print("Reference not found. Retrying...")
        time.sleep(RETRY_INTERVAL)
    return last


def annotate_match(match, path_name):
    screen = match["screen"].copy()
    x, y, w, h = match["x"], match["y"], match["width"], match["height"]
    cv2.rectangle(screen, (x, y), (x + w, y + h), (40, 180, 70), 3)
    cv2.putText(
        screen,
        f"{path_name} {match['confidence']:.2f}",
        (x, max(28, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (40, 180, 70),
        2,
        cv2.LINE_AA,
    )
    save_debug(f"match_{Path(path_name).stem}.png", screen)


# ============================================================
# CLICK TARGETS INSIDE A MATCH
# ============================================================

def radio_offsets(region):
    """Vertical stack of circular radios inside a matched crop."""
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 5)
    min_dim = min(region.shape[0], region.shape[1])
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(12, min_dim // 8),
        param1=90,
        param2=14,
        minRadius=max(4, min_dim // 30),
        maxRadius=max(10, min_dim // 8),
    )
    if circles is None:
        return []
    points = sorted(((int(x), int(y)) for x, y, _r in circles[0]), key=lambda p: p[1])
    if len(points) < 2:
        return []
    xs = [p[0] for p in points]
    if max(xs) - min(xs) > max(28, region.shape[1] * 0.35):
        return []
    return points


def white_input_offset(region):
    """Pale single-line field inside the property-checker crop."""
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 240), (180, 40, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    min_y = int(region.shape[0] * 0.40)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if y < min_y or h < 28 or h > 120 or w < 120:
            continue
        if area > best_area:
            best_area = area
            best = (x + min(w // 3, 90), y + h // 2)
    if best:
        return best
    return int(region.shape[1] * 0.28), int(region.shape[0] * 0.72)


def foreground_is(hwnd):
    return int(user32.GetForegroundWindow()) == int(hwnd)


def click_xy(x, y, hwnd=None):
    if hwnd:
        force_foreground(hwnd, stay_topmost=True)
    pyautogui.moveTo(x, y, duration=0.2)
    time.sleep(0.08)
    pyautogui.click()
    time.sleep(0.15)


def grab_keyboard(hwnd):
    """Put the browser in front so the next click can take keyboard focus."""
    if not hwnd:
        return
    force_foreground(hwnd, stay_topmost=True)
    if not foreground_is(hwnd):
        print("WARNING: browser still does not have keyboard focus")


def navy_button_below(screen, match):
    """Dark-blue submit control sitting just under the form crop."""
    y0 = min(screen.shape[0] - 1, match["y"] + match["height"])
    y1 = min(screen.shape[0], y0 + 160)
    x0 = max(0, match["x"])
    x1 = min(screen.shape[1], match["x"] + max(240, match["width"] // 2))
    strip = screen[y0:y1, x0:x1]
    if strip.size == 0:
        return None
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (95, 60, 30), (140, 255, 180))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if w < 70 or h < 24 or h > 80:
            continue
        if area > best_area:
            best_area = area
            best = (x0 + x + w // 2, y0 + y + h // 2)
    return best


def click_wide_radio(match, hwnd=None):
    region = match["screen"][
        match["y"] : match["y"] + match["height"],
        match["x"] : match["x"] + match["width"],
    ]
    radios = radio_offsets(region)
    if radios:
        local_x, local_y = radios[-1]
    else:
        local_x = int(match["width"] * 0.16)
        local_y = int(match["height"] * 0.78)
    target_x = match["x"] + local_x
    target_y = match["y"] + local_y
    print(f"Wide radio screen position: ({target_x}, {target_y})")
    grab_keyboard(hwnd)
    click_xy(target_x, target_y, hwnd=hwnd)
    return True


def click_postcode_field(match, hwnd=None):
    region = match["screen"][
        match["y"] : match["y"] + match["height"],
        match["x"] : match["x"] + match["width"],
    ]
    local_x, local_y = white_input_offset(region)
    target_x = match["x"] + local_x
    target_y = match["y"] + local_y
    print(f"Postcode field screen position: ({target_x}, {target_y})")
    grab_keyboard(hwnd)
    click_xy(target_x, target_y, hwnd=hwnd)
    time.sleep(0.1)
    pyautogui.click(target_x, target_y)
    time.sleep(0.15)
    return True


# ============================================================
# DOWNLOAD REFERENCE IMAGE FROM GOOGLE DRIVE
# ============================================================

def download_from_google_drive(file_id, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        print(f"Reference already exists: {output_path}")
        return True

    print("Downloading reference image...")
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        image = load_bgr(output_path)
        if image is None:
            print("Downloaded file is not a valid image.")
            return False
        print(f"Downloaded successfully: {output_path}")
        print(f"Image size: {image.shape[1]} x {image.shape[0]}")
        return True
    except Exception as error:
        print(f"Download failed: {error}")
        return False


def prepare_reference_images():
    print()
    print("========================================")
    print("PREPARING REFERENCE IMAGES")
    print("========================================")

    if not download_from_google_drive(REF1_FILE_ID, REF1_PATH):
        print("Could not prepare Reference 1.")
        return False
    if not download_from_google_drive(REF2_FILE_ID, REF2_PATH):
        print("Could not prepare Reference 2.")
        return False
    return True


# ============================================================
# TASK 1 - MEDIAWIKI
# ============================================================

def mediawiki_task():
    print()
    print("========================================")
    print("TASK 1: MEDIAWIKI")
    print("========================================")

    hwnd = open_site(
        MEDIAWIKI_URL,
        title_substrings=[
            "MediaWiki - Personal",
            "MediaWiki - Microsoft",
            "MediaWiki - Google Chrome",
            "MediaWiki - Mozilla",
        ],
        exclude_substrings=["Wikipedia", "grok", "mediawiki.org/wiki", "https://"],
        force_new=True,
        wait=max(PAGE_LOAD_WAIT, 7),
    )

    hidden = minimize_interfering_windows(keep_hwnd=hwnd)
    force_foreground(hwnd, stay_topmost=True) if hwnd else None
    pyautogui.press("esc")
    time.sleep(0.4)

    print("Locating Width section...")
    match = wait_for_reference(REF1_PATH, hwnd=hwnd)
    if match is None:
        print("ERROR: Could not locate reference image.")
        print("FAILED: Could not click Wide radio button.")
        save_debug("failed_mediawiki.png", take_screenshot())
        restore_windows(hidden)
        return False

    annotate_match(match, REF1_PATH.name)
    click_wide_radio(match, hwnd=hwnd)
    time.sleep(0.6)
    save_debug("after_mediawiki.png", take_screenshot())
    release_topmost(hwnd)
    restore_windows(hidden)
    print()
    print("SUCCESS: Wide radio button clicked.")
    return True


# ============================================================
# TASK 2 - PROPERTY CHECKER
# ============================================================

def property_checker_task():
    print()
    print("========================================")
    print("TASK 2: PROPERTY CHECKER")
    print("========================================")

    hwnd = open_site(
        PROPERTY_CHECKER_URL,
        title_substrings=["Property Checker", "propertychecker", "Check Property"],
        wait=PAGE_LOAD_WAIT,
        always_open=True,
    )

    hidden = minimize_interfering_windows(keep_hwnd=hwnd)
    force_foreground(hwnd, stay_topmost=True) if hwnd else None
    time.sleep(0.3)

    print("Locating postcode input...")
    match = wait_for_reference(REF2_PATH, hwnd=hwnd)
    if match is None:
        print("ERROR: Could not locate reference image.")
        print("FAILED: Could not locate postcode input.")
        save_debug("failed_property.png", take_screenshot())
        restore_windows(hidden)
        return False

    annotate_match(match, REF2_PATH.name)
    click_postcode_field(match, hwnd=hwnd)
    time.sleep(0.15)
    grab_keyboard(hwnd)

    print(f"Typing: {POSTCODE}")
    pyautogui.hotkey("ctrl", "a")
    pyautogui.press("backspace")
    pyautogui.write(POSTCODE, interval=0.05)
    time.sleep(0.3)
    save_debug("typed_property.png", take_screenshot())

    button = navy_button_below(match["screen"], match)
    if button:
        print(f"Check Now button: {button}")
        click_xy(button[0], button[1], hwnd=hwnd)
    else:
        grab_keyboard(hwnd)
        pyautogui.press("enter")

    time.sleep(1.0)
    save_debug("after_property.png", take_screenshot())
    release_topmost(hwnd)
    restore_windows(hidden)
    print()
    print("SUCCESS: Postcode entered.")
    return True


# ============================================================
# MAIN
# ============================================================

def main():
    make_dpi_aware()
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    DEBUG_DIR.mkdir(exist_ok=True)

    print()
    print("########################################")
    print("#     ALXICORN WEB MANIPULATOR         #")
    print("########################################")

    if not prepare_reference_images():
        print("Reference preparation failed.")
        return 1

    print()
    print("Reference images are ready.")
    print("Bringing the browser in front of this editor, then matching.")
    time.sleep(1)

    mediawiki_ok = mediawiki_task()
    time.sleep(2)
    property_ok = property_checker_task()

    print()
    print("========================================")
    print("ALXICORN WEB MANIPULATOR FINISHED")
    print("========================================")
    print(f"MediaWiki:        {'PASS' if mediawiki_ok else 'FAIL'}")
    print(f"Property Checker: {'PASS' if property_ok else 'FAIL'}")
    return 0 if mediawiki_ok and property_ok else 1


if __name__ == "__main__":
    sys.exit(main())
