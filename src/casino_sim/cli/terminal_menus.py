"""
Arrow-key horizontal menus (Windows / msvcrt) with ANSI styling, plus text fallbacks
on other platforms. Shared by interactive CLIs.
"""

from __future__ import annotations

import ctypes
import os
import re
import sys
from typing import Sequence

from casino_sim.cli.registry import StrategySpec

try:
    import msvcrt
except ImportError:
    msvcrt = None

RST = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

MENU_SEL_OPEN = "\033[1;30;106m"
MENU_SEL_CLOSE = RST
MENU_DIM = DIM

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
ansi_enabled = False


def visible_len(s: str) -> int:
    return len(ANSI_ESCAPE_RE.sub("", s))


def try_enable_windows_vt() -> bool:
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_vt = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | enable_vt)
        return True
    except (AttributeError, OSError, ValueError):
        return False


def ansi_should_work() -> bool:
    if os.name != "nt":
        return True
    if os.getenv("WT_SESSION") or os.getenv("ANSICON") or os.getenv("ConEmuANSI") == "ON":
        return True
    return try_enable_windows_vt()


def init_terminal(*, reconfigure_utf8: bool = True) -> None:
    global ansi_enabled
    if reconfigure_utf8 and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ansi_enabled = ansi_should_work()


def arrow_menus_available() -> bool:
    return msvcrt is not None and os.name == "nt" and sys.stdin.isatty()


def read_key() -> str:
    assert msvcrt is not None
    key = msvcrt.getch()
    if key in {b"\x00", b"\xe0"}:
        arrow = msvcrt.getch()
        if arrow == b"K":
            return "left"
        if arrow == b"M":
            return "right"
        return "other"
    if key in {b"\r", b"\n"}:
        return "enter"
    if key == b" ":
        return "space"
    if key in {b"a", b"A"}:
        return "left"
    if key in {b"d", b"D"}:
        return "right"
    return "other"


def _render_horizontal_single(
    options: Sequence[tuple[str, str]], selected_index: int
) -> str:
    rendered: list[str] = []
    for idx, (_, label) in enumerate(options):
        if idx == selected_index:
            selected_text = f"[ {label} ]"
            if ansi_enabled:
                rendered.append(f"{MENU_SEL_OPEN}{selected_text}{MENU_SEL_CLOSE}")
            else:
                rendered.append(selected_text)
        else:
            if ansi_enabled:
                rendered.append(f"{MENU_DIM}  {label}  {RST}")
            else:
                rendered.append(f"  {label}  ")
    return " | ".join(rendered)


def select_from_menu_fallback(title: str, options: list[tuple[str, str]]) -> str:
    print(f"\n{title}")
    for i, (_, label) in enumerate(options, start=1):
        print(f"  {i}) {label}")
    n = len(options)
    while True:
        raw = input("Enter choice number: ").strip()
        if not raw.isdigit():
            print(f"Enter a number from 1 to {n}.")
            continue
        choice = int(raw)
        if choice < 1 or choice > n:
            print(f"Enter a number from 1 to {n}.")
            continue
        return options[choice - 1][0]


def select_from_menu(title: str, options: list[tuple[str, str]]) -> str:
    if not arrow_menus_available() or len(options) == 0:
        return select_from_menu_fallback(title, options)

    t = f"{CYAN}{BOLD}{title}{RST}" if ansi_enabled else title
    hint = (
        f"{DIM}Use LEFT/RIGHT arrows (or A/D), ENTER to confirm.{RST}"
        if ansi_enabled
        else "Use LEFT/RIGHT arrows (or A/D), ENTER to confirm."
    )
    print(f"\n{t}")
    print(hint)
    selected = 0
    last_visible_len = 0
    while True:
        line = _render_horizontal_single(options, selected)
        padding = max(0, last_visible_len - visible_len(line))
        sys.stdout.write("\r" + line + (" " * padding))
        sys.stdout.flush()
        last_visible_len = visible_len(line)

        key = read_key()
        if key == "left":
            selected = (selected - 1) % len(options)
            continue
        if key == "right":
            selected = (selected + 1) % len(options)
            continue
        if key == "enter":
            sys.stdout.write("\n")
            sys.stdout.flush()
            return options[selected][0]


def _truncate_label(label: str, max_len: int = 28) -> str:
    if len(label) <= max_len:
        return label
    return label[: max_len - 1] + "…"


def _render_strategy_multiselect_line(
    specs: tuple[StrategySpec, ...],
    selected: set[int],
    cursor: int,
) -> str:
    n = len(specs)
    parts: list[str] = []

    def wrap_cell(core: str, is_cursor: bool, is_chosen: bool) -> str:
        if is_cursor:
            inner = f" {core} "
            if ansi_enabled:
                return f"{MENU_SEL_OPEN}[{inner}]{MENU_SEL_CLOSE}"
            return f"[{inner}]"
        if ansi_enabled:
            if is_chosen:
                return f"{GREEN}{BOLD} {core} {RST}"
            return f"{MENU_DIM} {core} {RST}"
        return f"  {core}  "

    for i in range(n):
        tag = "[+]" if i in selected else "[ ]"
        lab = _truncate_label(specs[i].label)
        core = f"{tag} {lab}"
        parts.append(wrap_cell(core, cursor == i, i in selected))

    all_lab = "All strategies"
    parts.append(wrap_cell(all_lab, cursor == n, False))

    conf_lab = "Confirm"
    parts.append(wrap_cell(conf_lab, cursor == n + 1, False))

    return " | ".join(parts)


def select_strategy_indices_multimenu_fallback(
    specs: tuple[StrategySpec, ...],
) -> list[int]:
    print("\n--- Strategies ---")
    for i, s in enumerate(specs, start=1):
        print(f"  {i}) {s.label}")
    n = len(specs)
    while True:
        raw = input(
            "\nEnter strategy numbers (e.g. 1 3), or type ALL for every strategy: "
        ).strip()
        low = raw.lower()
        if low == "all":
            return list(range(n))
        parts = [p for p in raw.replace(",", " ").split() if p.strip()]
        if not parts:
            print("Enter at least one number, or ALL.")
            continue
        out: list[int] = []
        try:
            for p in parts:
                v = int(p)
                if v < 1 or v > n:
                    raise ValueError(f"out of range: {v}")
                out.append(v - 1)
        except ValueError as e:
            print(f"Invalid: {e}")
            continue
        return sorted(set(out))


def select_strategy_indices_multimenu(
    specs: tuple[StrategySpec, ...],
) -> list[int]:
    """Return 0-based indices of strategies to run. ``specs`` may not be empty."""
    n = len(specs)
    if n == 0:
        return []
    if not arrow_menus_available():
        return select_strategy_indices_multimenu_fallback(specs)

    title = f"{CYAN}{BOLD}Select strategies to simulate{RST}" if ansi_enabled else "Select strategies to simulate"
    hint = (
        f"{DIM}LEFT/RIGHT move · SPACE toggles strategy · ENTER on All runs all · "
        f"ENTER on Confirm runs selection (needs ≥1).{RST}"
        if ansi_enabled
        else (
            "LEFT/RIGHT move · SPACE toggles strategy · ENTER on All runs all · "
            "ENTER on Confirm runs selection (needs ≥1)."
        )
    )
    print(f"\n{title}")
    print(hint)

    selected: set[int] = set()
    cursor = 0
    total_slots = n + 2
    last_visible_len = 0

    while True:
        line = _render_strategy_multiselect_line(specs, selected, cursor)
        padding = max(0, last_visible_len - visible_len(line))
        sys.stdout.write("\r" + line + (" " * padding))
        sys.stdout.flush()
        last_visible_len = visible_len(line)

        key = read_key()
        if key == "left":
            cursor = (cursor - 1) % total_slots
            continue
        if key == "right":
            cursor = (cursor + 1) % total_slots
            continue
        if key == "space" or (key == "enter" and cursor < n):
            if cursor < n:
                if cursor in selected:
                    selected.remove(cursor)
                else:
                    selected.add(cursor)
            continue
        if key == "enter" and cursor == n:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return list(range(n))
        if key == "enter" and cursor == n + 1:
            if selected:
                sys.stdout.write("\n")
                sys.stdout.flush()
                return sorted(selected)
            if os.name == "nt":
                print("\a", end="", flush=True)
            continue


def prompt_int(prompt: str, minimum: int = 1) -> int:
    styled_prompt = f"{BLUE}{prompt}{RST}" if ansi_enabled else prompt
    warn = YELLOW if ansi_enabled else ""
    rst = RST if ansi_enabled else ""
    while True:
        value_raw = input(styled_prompt).strip()
        try:
            value = int(value_raw)
        except ValueError:
            print(f"{warn}Enter a whole number.{rst}")
            continue
        if value < minimum:
            print(f"{warn}Must be at least {minimum}.{rst}")
            continue
        return value


def prompt_float(prompt: str, minimum: float) -> float:
    styled_prompt = f"{BLUE}{prompt}{RST}" if ansi_enabled else prompt
    warn = YELLOW if ansi_enabled else ""
    rst = RST if ansi_enabled else ""
    while True:
        value_raw = input(styled_prompt).strip()
        try:
            value = float(value_raw)
        except ValueError:
            print(f"{warn}Enter a number.{rst}")
            continue
        if value < minimum:
            print(f"{warn}Must be at least {minimum}.{rst}")
            continue
        return value
