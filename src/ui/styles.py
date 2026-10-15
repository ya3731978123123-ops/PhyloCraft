"""
PhyloCraft Modern Studio Stylesheet
Modern Precision Scientific Desktop Aesthetics:
- Canvas background: Clean light neutral slate (#F8FAFC)
- Panels & Insets: Pure white (#FFFFFF)
- Borders: Crisp subtle slate (#E2E8F0 / #CBD5E1)
- Primary & Action Accents: Emerald / Modern Teal (#008287 / #0D9488)
- Smooth 5px-6px corner radius for modern desktop software experience.
"""

MODERN_STYLE = """
/* Global Window & Typography */
QWidget {
    background-color: #F8FAFC;
    color: #0F172A;
    font-family: "Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC", "Segoe UI", sans-serif;
    font-size: 12px;
    selection-background-color: #008287;
    selection-color: #FFFFFF;
}

/* Native Menu Bar & Menus */
QMenuBar {
    background-color: #FFFFFF;
    color: #1E293B;
    border-bottom: 1px solid #E2E8F0;
    font-size: 12px;
    padding: 2px 6px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #F1F5F9;
    color: #008287;
}

QMenu {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 4px 0px;
    font-size: 12px;
}

QMenu::item {
    padding: 6px 26px 6px 20px;
    color: #1E293B;
}

QMenu::item:selected {
    background-color: #008287;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: #E2E8F0;
    margin: 4px 6px;
}

/* Tooltips */
QToolTip {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11px;
}

/* Main Content Area */
QStackedWidget#content_area {
    background-color: #F8FAFC;
    padding: 4px;
}

/* Group Boxes / Scientific Property Frames */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    margin-top: 20px;
    padding: 14px 12px 10px 12px;
    font-weight: bold;
    color: #008287;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    color: #008287;
    font-weight: bold;
}

/* Standard Push Buttons */
QPushButton {
    background-color: #FFFFFF;
    color: #1E293B;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    padding: 5px 14px;
    font-weight: 500;
    font-size: 12px;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #F1F5F9;
    border-color: #94A3B8;
    color: #008287;
}

QPushButton:pressed {
    background-color: #E2E8F0;
}

QPushButton:disabled {
    background-color: #F8FAFC;
    border-color: #E2E8F0;
    color: #94A3B8;
}

/* Primary Action Buttons (Teal) */
QPushButton#primary_button {
    background-color: #008287;
    color: #FFFFFF;
    font-weight: bold;
    border: 1px solid #00666B;
    border-radius: 4px;
    padding: 6px 16px;
}

QPushButton#primary_button:hover {
    background-color: #006F73;
    border-color: #005457;
    color: #FFFFFF;
}

QPushButton#primary_button:pressed {
    background-color: #005457;
}

QPushButton#primary_button:disabled {
    background-color: #CBD5E1;
    border-color: #94A3B8;
    color: #FFFFFF;
}

/* Danger / Stop Buttons */
QPushButton#danger_button {
    background-color: #EF4444;
    color: #FFFFFF;
    font-weight: bold;
    border: 1px solid #DC2626;
    border-radius: 4px;
    padding: 5px 14px;
}

QPushButton#danger_button:hover {
    background-color: #DC2626;
    color: #FFFFFF;
}

QPushButton#danger_button:pressed {
    background-color: #B91C1C;
}

QPushButton#danger_button:disabled {
    background-color: #F1F5F9;
    border-color: #E2E8F0;
    color: #94A3B8;
}

/* Line Edit & Form Inputs (Crisp Inset Look) */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    padding: 4px 8px;
    color: #0F172A;
    font-size: 12px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #008287;
    background-color: #FFFFFF;
}

QLineEdit::placeholder {
    color: #94A3B8;
}

/* Combobox (Crisp Select Look with Down Arrow) */
QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    padding: 3px 24px 3px 8px;
    color: #0F172A;
    font-size: 12px;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #008287;
}

QComboBox:focus {
    border: 1px solid #008287;
    background-color: #FFFFFF;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}

QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #64748B;
    margin-right: 6px;
}

QComboBox::down-arrow:hover {
    border-top-color: #008287;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    selection-background-color: #E0F2F1;
    selection-color: #008287;
    padding: 4px;
    border-radius: 4px;
    color: #0F172A;
}

/* Progress Bar */
QProgressBar {
    background-color: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 4px;
    height: 16px;
    text-align: center;
    color: #0F172A;
    font-size: 11px;
    font-weight: 500;
}

QProgressBar::chunk {
    background-color: #008287;
    border-radius: 3px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #F8FAFC;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #CBD5E1;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #F8FAFC;
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #CBD5E1;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #94A3B8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Tables */
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    gridline-color: #F1F5F9;
    color: #1E293B;
}

QTableWidget::item {
    padding: 5px;
    border-bottom: 1px solid #F1F5F9;
}

QTableWidget::item:selected {
    background-color: #E0F2F1;
    color: #008287;
}

QHeaderView::section {
    background-color: #F1F5F9;
    color: #1E293B;
    font-weight: bold;
    border: none;
    border-bottom: 1px solid #CBD5E1;
    border-right: 1px solid #CBD5E1;
    padding: 6px;
    font-size: 11px;
}

/* Checkboxes */
QCheckBox {
    spacing: 6px;
    color: #1E293B;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #CBD5E1;
    background-color: #FFFFFF;
}

QCheckBox::indicator:hover {
    border-color: #008287;
}

QCheckBox::indicator:checked {
    background-color: #008287;
    border-color: #00666B;
}

/* Tab Headers inside views */
QTabWidget::pane {
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    background-color: #FFFFFF;
    padding: 6px;
}

QTabBar::tab {
    background-color: #F1F5F9;
    color: #475569;
    padding: 6px 14px;
    border: 1px solid #CBD5E1;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 3px;
    font-weight: 500;
}

QTabBar::tab:hover {
    color: #008287;
    background-color: #FFFFFF;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #008287;
    font-weight: bold;
    border-top: 2px solid #008287;
}
"""
