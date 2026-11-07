"""Record the owner's UI journeys on an isolated CPU-rendered Android emulator.

Requires the current tree's debug build with -PbenchAppId=com.ngdtuanh.abook.ledgerui.
Never selects a physical device or the default adb server. Videos use the device
clock; host command latency is deliberately not reported as animation duration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET


class Audit:
    def __init__(self, device: str, output: Path):
        if not re.fullmatch(r"emulator-\d+", device):
            raise ValueError("An explicit emulator serial is required")
        self.prefix = ["adb", "-P", "5038", "-s", device]
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.events: list[dict] = []
        self.started = time.monotonic()
        if self.adb("shell", "getprop", "ro.kernel.qemu").strip() != b"1":
            raise ValueError("The selected device is not an emulator")

    def adb(self, *args: str) -> bytes:
        return subprocess.check_output(self.prefix + list(args), creationflags=subprocess.CREATE_NO_WINDOW)

    def nodes(self):
        for attempt in range(4):
            result = self.adb("shell", "uiautomator", "dump", "/sdcard/ledgerui.xml")
            if b"dumped" in result:
                return ET.fromstring(self.adb("exec-out", "cat", "/sdcard/ledgerui.xml"))
            time.sleep(.3)
        raise RuntimeError("uiautomator could not read the current window")

    def save(self, name: str):
        root = self.nodes()
        (self.output / f"{name}.xml").write_bytes(ET.tostring(root, encoding="utf-8"))
        (self.output / f"{name}.png").write_bytes(self.adb("exec-out", "screencap", "-p"))
        anchors = {n.get("resource-id"): n.get("bounds") for n in root.iter("node") if n.get("resource-id")}
        self.events.append(dict(name=name, hostTime=time.monotonic() - self.started, anchors=anchors))
        (self.output / "journeys.json").write_text(json.dumps(self.events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(name, flush=True)

    def tap(self, tag: str):
        node = next((n for n in self.nodes().iter("node") if tag in
                     (n.get("resource-id"), n.get("text"), n.get("content-desc"))), None)
        if node is None:
            raise RuntimeError(f"No visible node {tag}")
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds", "")))
        self.adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
        time.sleep(.45)

    def back(self):
        self.adb("shell", "input", "keyevent", "4")
        time.sleep(.45)

    def record(self, name: str, action):
        remote = f"/sdcard/ledgerui-{name}.mp4"
        process = subprocess.Popen(self.prefix + ["shell", "screenrecord", "--bit-rate", "6000000", "--time-limit", "120", remote],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(.6)
        try:
            action()
        finally:
            # Only this emulator is selected, and its screenrecord belongs to this audit.
            pids = subprocess.run(self.prefix + ["shell", "pidof", "screenrecord"], capture_output=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode().split()
            for pid in pids:
                if pid.isdecimal():
                    self.adb("shell", "kill", "-2", pid)
            process.wait(timeout=15)
            self.adb("pull", remote, str(self.output / f"{name}.mp4"))

    def navigation(self):
        self.save("library")
        self.tap("book_cell"); self.save("book")
        self.tap("book_back"); self.save("book-back")
        for tag in ("tab_settings", "tab_studio", "tab_library"):
            self.tap(tag); self.save(tag)
        self.tap("tab_settings")
        self.tap("Giao diện"); self.save("settings-child")
        self.back(); self.save("settings-back")
        self.tap("tab_library")
        # Horizontal library filters exercise the same gesture family as tab panels.
        self.tap("filter_listening"); self.save("filter-listening")
        self.tap("filter_all"); self.save("filter-all")

    def player(self):
        self.tap("book_cell"); self.tap("book_primary"); self.save("resume-book")
        self.tap("book_back"); self.save("mini")
        self.tap("mini_player")
        if any(n.get("content-desc") == "Phát" for n in self.nodes().iter("node")):
            self.tap("Phát")
        self.save("playing")
        self.tap("Tạm dừng"); self.save("paused")
        self.tap("Phát"); self.save("resumed")
        self.tap("mode_read"); self.save("reading")
        self.tap("mode_listen"); self.save("listening")

    def sheets(self):
        for tag in ("player_more", "player_speed", "player_sleep"):
            self.tap(tag); self.save(tag)
            self.back(); self.save(tag + "-back")
        self.tap("mode_read")
        self.tap("player_more"); self.save("reading-more")
        self.back(); self.save("reading-more-back")
        self.tap("mode_listen")
        self.tap("collapse_player"); self.save("mini-return")

    def tabs(self):
        self.tap("book_cell"); self.save("book-tabs-chapters")
        self.tap("book_tab_history"); self.save("book-tabs-history")
        self.tap("book_tab_cast"); self.save("book-tabs-cast")
        self.tap("book_tab_chapters"); self.save("book-tabs-chapters-return")
        self.adb("shell", "input", "swipe", "900", "1450", "150", "1450", "240")
        self.save("book-tabs-horizontal-gesture")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--only", choices=["all", "tabs"], default="all")
    args = parser.parse_args()
    audit = Audit(args.device, args.output)
    audit.adb("shell", "am", "force-stop", "com.ngdtuanh.abook.ledgerui")
    audit.adb("shell", "am", "start", "-n", "com.ngdtuanh.abook.ledgerui/vn.abook.player.ui.NativeActivity", "--ei", "abook.demo.books", "12")
    time.sleep(2)
    if args.only == "tabs":
        audit.record("book-tabs", audit.tabs)
    else:
        audit.record("navigation", audit.navigation)
        audit.record("player", audit.player)
        audit.record("sheets", audit.sheets)


if __name__ == "__main__":
    main()
