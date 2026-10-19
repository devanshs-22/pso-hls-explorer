"""Reusable widgets: step cards, status tiles, output buttons, chart views, tables, KPI tiles."""
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)


def repolish(*widgets):
    """Re-apply the style sheet after a dynamic property changed."""
    for w in widgets:
        w.style().unpolish(w)
        w.style().polish(w)
        w.update()


def label(text, name=None, wrap=False, rich=False):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if rich:
        lab.setTextFormat(Qt.TextFormat.RichText)
    return lab


def button(text, name="Secondary", slot=None, tip=None):
    b = QPushButton(text)
    b.setObjectName(name)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    return b


class StepCard(QFrame):
    """One numbered step of the input panel: locked (grey) until the previous step is done."""

    def __init__(self, number, title, description):
        super().__init__()
        self.setObjectName("StepCard")
        self.number = number
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(10)
        self.num = label(str(number), "StepNum")
        self.title = label(title, "StepTitle")
        head.addWidget(self.num, 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(self.title, 1)
        self.check = label("", "StepResult")
        head.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(head)
        self.desc = label(description, "StepDesc", wrap=True)
        outer.addWidget(self.desc)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 4, 0, 0)
        self.body_layout.setSpacing(8)
        outer.addWidget(self.body)
        self.lock = label(f"Locked — finish step {number - 1} first" if number > 1 else "", "StepLock")
        outer.addWidget(self.lock)
        self.result = label("", "StepResult", wrap=True)
        self.result.hide()
        outer.addWidget(self.result)
        self.set_state("locked" if number > 1 else "active")

    def set_state(self, state):
        self.state = state
        for w in (self, self.num, self.title, self.desc):
            w.setProperty("state", state)
        repolish(self, self.num, self.title, self.desc)
        self.body.setEnabled(state != "locked")
        self.lock.setVisible(state == "locked" and self.number > 1)
        self.num.setText("✓" if state == "done" else str(self.number))
        if state != "done":
            self.result.hide()

    def set_result(self, text):
        self.result.setText("✓  " + text)
        self.result.show()


class StatusTile(QFrame):
    STATE_TEXT = {"waiting": "WAITING", "next": "DO THIS NEXT", "running": "RUNNING…", "done": "DONE ✓",
                  "error": "ERROR"}

    def __init__(self, number, title):
        super().__init__()
        self.setObjectName("StatusTile")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        self.state_lab = label("", "TileState")
        self.title = label(f"{number} · {title}", "TileTitle")
        self.detail = label("", "TileDetail", wrap=True)
        lay.addWidget(self.state_lab)
        lay.addWidget(self.title)
        lay.addWidget(self.detail)
        self.set_state("waiting", "")

    def set_state(self, state, detail=None):
        for w in (self, self.state_lab, self.title):
            w.setProperty("state", state)
        repolish(self, self.state_lab, self.title)
        self.state_lab.setText(self.STATE_TEXT[state])
        if detail is not None:
            self.detail.setText(detail)
            self.detail.setVisible(bool(detail))


def _icon(draw, colour, size=48):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw(p, QColor(colour), size / 24)
    p.end()
    return QIcon(pm)


def _draw_lock(p, c, s):
    p.setPen(QPen(c, 2.2 * s))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(7 * s, 3 * s, 10 * s, 12 * s), 0, 180 * 16)
    p.drawLine(QPointF(7 * s, 9 * s), QPointF(7 * s, 11 * s))
    p.drawLine(QPointF(17 * s, 9 * s), QPointF(17 * s, 11 * s))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    p.drawRoundedRect(QRectF(4.5 * s, 10.5 * s, 15 * s, 11 * s), 2.5 * s, 2.5 * s)


def _draw_open(p, c, s):
    pen = QPen(c, 2.2 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath(QPointF(11 * s, 4 * s))
    path.lineTo(QPointF(5 * s, 4 * s))
    path.lineTo(QPointF(5 * s, 19 * s))
    path.lineTo(QPointF(20 * s, 19 * s))
    path.lineTo(QPointF(20 * s, 13 * s))
    p.drawPath(path)
    p.drawLine(QPointF(11 * s, 13 * s), QPointF(20 * s, 4 * s))
    p.drawLine(QPointF(14 * s, 4 * s), QPointF(20 * s, 4 * s))
    p.drawLine(QPointF(20 * s, 4 * s), QPointF(20 * s, 10 * s))


class OutputButton(QPushButton):
    def __init__(self, text, tip):
        super().__init__(text.replace("&", "&&"))
        self.setObjectName("OutBtn")
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(15, 15))
        self.setMinimumHeight(38)
        self._lock = _icon(_draw_lock, "#b3bac6")
        self._open = _icon(_draw_open, "#2563eb")
        self.set_available(False)

    def set_available(self, ok, fresh=False):
        self.setEnabled(ok)
        self.setIcon(self._open if ok else self._lock)
        self.setProperty("fresh", bool(ok and fresh))
        repolish(self)


class FigureView(QWidget):
    """A matplotlib Figure with a "Save image…" button. scroll=True keeps the figure at its
    natural size (scrollbars when the window is smaller); otherwise it stretches to fit."""

    def __init__(self, fig, scroll=False, filename="figure.png"):
        super().__init__()
        self.fig, self.filename = fig, filename
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.canvas = FigureCanvasQTAgg(fig)
        if scroll:
            w, h = fig.get_size_inches() * fig.dpi
            self.canvas.setMinimumSize(int(w), int(h))
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setWidget(self.canvas)
            area.setFrameShape(QFrame.Shape.NoFrame)
            lay.addWidget(area, 1)
        else:
            self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            lay.addWidget(self.canvas, 1)
        bar = QHBoxLayout()
        bar.addStretch(1)
        bar.addWidget(button("Save image…", "Secondary", self.save, "Save this chart as a PNG or PDF file"))
        lay.addLayout(bar)

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save image", self.filename,
                                              "PNG image (*.png);;PDF document (*.pdf);;SVG image (*.svg)")
        if path:
            self.fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=self.fig.get_facecolor())


def table(headers, rows, stretch_last=True, row_headers=None, mono_cols=(), align_right=(), fit=True,
          stretch_all=False):
    """Read-only QTableWidget filled with rows of strings (or (text, tooltip) tuples).
    fit=True: small tables are only as tall as their rows (no empty white space)."""
    t = QTableWidget(len(rows), len(headers))
    t.setHorizontalHeaderLabels(headers)
    if row_headers:
        t.setVerticalHeaderLabels(row_headers)
    else:
        t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(False)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            tip = None
            if isinstance(val, tuple):
                val, tip = val
            it = QTableWidgetItem(str(val))
            if tip:
                it.setToolTip(tip)
            if c in align_right:
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if c in mono_cols:
                f = it.font()
                f.setFamily("Menlo")
                it.setFont(f)
            t.setItem(r, c, it)
    hdr = t.horizontalHeader()
    hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch if stretch_all else QHeaderView.ResizeMode.ResizeToContents)
    if stretch_last:
        hdr.setStretchLastSection(True)
    t.verticalHeader().setDefaultSectionSize(28)
    if fit and 0 < len(rows) <= 16:
        t.setFixedHeight(hdr.sizeHint().height() + 28 * len(rows) + 2 * t.frameWidth() + 12)
    return t


class Kpi(QFrame):
    def __init__(self, title, value, sub="", hero=False):
        super().__init__()
        self.setObjectName("Kpi")
        self.setProperty("hero", hero)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(0)
        lay.addWidget(label(title, "KpiLabel"))
        lay.addWidget(label(value, "KpiValue"))
        lay.addWidget(label(sub, "KpiSub"))


def card(title=None):
    """A white rounded card; returns (frame, inner layout)."""
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(8)
    if title:
        lay.addWidget(label(title, "CardTitle"))
    return f, lay
