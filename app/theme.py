# 配色与样式：深色编辑器风，语义色见方案
COLORS = {
    "bg": "#0B1020",
    "panel": "#111827",
    "panel2": "#0F172A",
    "border": "#1F2937",
    "border2": "#374151",
    "text": "#E5E7EB",
    "muted": "#94A3B8",
    "info": "#22D3EE",
    "ok": "#34D399",
    "warn": "#FBBF24",
    "err": "#F87171",
    "accent": "#A78BFA",
}

LIGHT = {
    "bg": "#F8FAFC",
    "panel": "#FFFFFF",
    "panel2": "#F1F5F9",
    "border": "#E2E8F0",
    "border2": "#CBD5E1",
    "text": "#0F172A",
    "muted": "#64748B",
    "info": "#0891B2",
    "ok": "#059669",
    "warn": "#B45309",
    "err": "#DC2626",
    "accent": "#7C3AED",
}


def palette(theme: str) -> dict:
    return COLORS if theme != "light" else LIGHT


def qss(theme: str) -> str:
    c = palette(theme)
    return f"""
QWidget {{
    background: {c['bg']};
    color: {c['text']};
    font-family: "Microsoft YaHei UI", "Segoe UI", "Noto Sans SC";
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QFrame#card {{
    background: {c['panel']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QLabel#muted {{ color: {c['muted']}; }}
QLabel#title {{ font-size: 20px; font-weight: 700; }}
QLabel#big {{ font-size: 16px; font-weight: 600; }}
QLabel#mono, QLineEdit#mono {{
    font-family: "Cascadia Mono", "JetBrains Mono", Consolas, monospace;
}}
QLineEdit, QComboBox {{
    background: {c['panel2']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {c['info']};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {c['info']}; }}
QPushButton {{
    background: {c['panel2']};
    border: 1px solid {c['border2']};
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {c['info']}; color: {c['info']}; }}
QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}
QPushButton#primary {{
    background: {c['info']};
    color: {c['bg']};
    border: none;
    font-weight: 700;
}}
QPushButton#primary:hover {{ background: {c['accent']}; color: {c['bg']}; }}
QProgressBar {{
    background: {c['panel2']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {c['info']}; border-radius: 6px; }}
QListWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
QListWidget::item:selected {{ background: {c['panel2']}; color: {c['info']}; }}
QCheckBox {{ spacing: 8px; }}
QScrollBar:vertical {{ background: {c['panel2']}; width: 10px; border-radius: 5px; }}
QScrollBar::handle:vertical {{ background: {c['border2']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {c['panel2']}; color: {c['text']}; border: 1px solid {c['border2']}; }}
QFrame#card:hover {{ border-color: {c['border2']}; }}
QFrame#card[clickable="true"]:hover {{ border-color: {c['info']}; }}
QPushButton:pressed {{ padding-top: 8px; padding-bottom: 4px; }}
QListWidget::item:hover {{ background: {c['panel2']}; }}
"""
