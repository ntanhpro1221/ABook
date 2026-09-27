import sys


if __name__ == "__main__":
    if "--classic" in sys.argv[1:]:
        # Giao diện cũ (Qt thuần, gui.py): lối lui khi cửa sổ mới có vấn đề.
        from ebook_reader.gui import run_gui

        raise SystemExit(run_gui())
    # Cửa sổ ABook (giao diện web trong Qt WebEngine, desktop.py); mở kèm file .abook thì mở thẳng cuốn ấy.
    from ebook_reader.desktop import run_desktop

    raise SystemExit(run_desktop())
