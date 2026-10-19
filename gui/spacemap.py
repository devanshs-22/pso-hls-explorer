"""Animated design-space map and the live convergence strip used by the PSO replay window."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from psodse.report import config_text

from . import theme

LO, HI = QColor("#eaf2fc"), QColor("#1d5eb0")


def lerp_colour(a, b, t):
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


class SpaceMap(QWidget):
    """Every square is one design (rows = adders, columns = multipliers). Squares light up
    with their cost once the swarm has visited them; numbered dots are the particles."""

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(420, 220)
        self.ex = None
        self.frames, self.cur, self.prev, self.t = [], 0, 0, 1.0
        self.anim = QVariantAnimation(self)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.valueChanged.connect(self._tick)

    def set_data(self, ex, frames):
        self.ex, self.frames, self.cur, self.prev, self.t = ex, frames, 0, 0, 1.0
        costs = [p.cost for p in ex.all_points]
        self.cmin, self.cmax = min(costs), max(costs)
        self.cost_of = {p.position: p for p in ex.all_points}
        self.update()

    def show_frame(self, i, animate, duration=550):
        self.anim.stop()
        self.prev, self.cur = (self.cur, i) if animate else (i, i)
        if animate:
            self.t = 0.0
            self.anim.setDuration(duration)
            self.anim.start()
        else:
            self.t = 1.0
            self.update()

    def _tick(self, v):
        self.t = float(v)
        self.update()

    # -- geometry ----------------------------------------------------------------
    def _axes(self):
        ex = self.ex
        d2 = len(ex.dims) >= 2
        rows = list(range(ex.probe.lower[0], ex.probe.upper[0] + 1)) if d2 else [None]
        ci = 1 if d2 else 0
        cols = list(range(ex.probe.lower[ci], ex.probe.upper[ci] + 1))
        return d2, rows, cols

    def _geom(self):
        d2, rows, cols = self._axes()
        left, top, pad = (78 if d2 else 22), 58, 12
        cw = min(120.0, (self.width() - left - pad) / len(cols))
        ch = min(96.0, max(56.0, cw * 0.78), (self.height() - top - pad) / len(rows))
        cw = max(cw, 40.0)
        gx = left + max(0.0, (self.width() - left - pad - cw * len(cols)) / 2)
        return d2, rows, cols, gx, top, cw, ch

    def _cell_rect(self, pos, g=None):
        d2, rows, cols, gx, top, cw, ch = g or self._geom()
        r = rows.index(pos[0]) if d2 else 0
        c = cols.index(pos[1] if d2 else pos[0])
        return QRectF(gx + c * cw, top + r * ch, cw, ch)

    def _particle_xy(self, frame, i, g):
        """Particles on the same design share its square in a small grid below the cost label."""
        pos = frame.positions[i]
        rect = self._cell_rect(pos, g)
        same = [j for j, p in enumerate(frame.positions) if p == pos]
        slot, m = same.index(i), len(same)
        aw, ah, top = rect.width() - 12, rect.height() - 30, rect.top() + 24
        best = (1, 0.0)
        for per_row in range(1, m + 1):
            n_rows = math.ceil(m / per_row)
            pitch = min(aw / per_row, ah / n_rows)
            if pitch > best[1]:
                best = (per_row, pitch)
        per_row, pitch = best
        n_rows = math.ceil(m / per_row)
        row = slot // per_row
        in_row = m - per_row * (n_rows - 1) if row == n_rows - 1 else per_row
        x = rect.center().x() + (slot % per_row - (in_row - 1) / 2) * pitch
        y = top + ah / 2 + (row - (n_rows - 1) / 2) * pitch
        return QPointF(x, y), min(1.0, pitch / 25)

    # -- painting ------------------------------------------------------------------
    def paintEvent(self, _):
        if not self.ex or not self.frames:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = self._geom()
        d2, rows, cols, gx, top, cw, ch = g
        f, fp = self.frames[self.cur], self.frames[self.prev]
        small, bold = QFont(), QFont()
        small.setPixelSize(11)
        bold.setPixelSize(12)
        bold.setBold(True)

        # axis labels
        p.setFont(small)
        p.setPen(QColor(theme.INK_2))
        col_dim = self.ex.dims[1 if d2 else 0]
        p.drawText(QRectF(gx, 6, 400, 18), Qt.AlignmentFlag.AlignLeft, f"number of {col_dim}s →")
        if d2:
            p.drawText(QRectF(4, top - 26, gx - 8, 18), Qt.AlignmentFlag.AlignLeft, f"{self.ex.dims[0]}s ↓")
        p.setFont(bold)
        p.setPen(QColor(theme.INK))
        for c, v in enumerate(cols):
            p.drawText(QRectF(gx + c * cw, top - 26, cw, 20), Qt.AlignmentFlag.AlignCenter, str(v))
        if d2:
            for r, v in enumerate(rows):
                p.drawText(QRectF(gx - 40, top + r * ch, 30, ch), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(v))

        # cells
        extra = tuple(self.ex.probe.lower[2:])
        for r, rv in enumerate(rows):
            for c, cv in enumerate(cols):
                pos = ((rv, cv) + extra) if d2 else (cv,)
                rect = QRectF(gx + c * cw + 2, top + r * ch + 2, cw - 4, ch - 4)
                design = self.cost_of.get(pos)
                seen = pos in f.visited and design is not None
                if seen:
                    t = (design.cost - self.cmin) / (self.cmax - self.cmin) if self.cmax > self.cmin else 0.5
                    fill, ink = lerp_colour(LO, HI, 0.08 + 0.92 * t), QColor("#ffffff" if t > 0.55 else theme.INK)
                else:
                    fill, ink = QColor("#f1f3f6"), QColor(theme.MUTED)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fill)
                p.drawRoundedRect(rect, 8, 8)
                p.setFont(small)
                p.setPen(ink)
                p.drawText(rect.adjusted(7, 4, -4, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                           f"{design.cost:.3f}" if seen else "?")

        k = self.t
        # global best ring (moves smoothly)
        ra, rb = self._cell_rect(fp.gbest, g), self._cell_rect(f.gbest, g)
        ring = QRectF(ra.x() + (rb.x() - ra.x()) * k, ra.y() + (rb.y() - ra.y()) * k, cw, ch).adjusted(1, 1, -1, -1)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(theme.INK), 2.6))
        p.drawRoundedRect(ring, 9, 9)
        star = QFont()
        star.setPixelSize(17)
        p.setFont(star)
        p.setPen(QColor(theme.MULT))
        p.drawText(ring.adjusted(0, 0, -6, -3), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, "★")

        # trails from the previous frame
        if self.prev != self.cur and f.phase in ("move", "mutate"):
            pen = QPen(QColor(235, 104, 52, 120), 2)
            if f.phase == "mutate":
                pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            for i in range(len(f.positions)):
                a, _ = self._particle_xy(fp, i, g)
                b, _ = self._particle_xy(f, i, g)
                if (a - b).manhattanLength() > 2:
                    p.drawLine(a, b)

        # particles
        lab = QFont()
        lab.setBold(True)
        self._hit = []
        for i in range(len(f.positions)):
            a, sa = self._particle_xy(fp, i, g)
            b, sb = self._particle_xy(f, i, g)
            pt = a + (b - a) * k
            s = sa + (sb - sa) * k
            r = 11.5 * s
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.setBrush(QColor(theme.MULT))
            p.drawEllipse(pt, r, r)
            lab.setPixelSize(max(7, int(10 * s)))
            p.setFont(lab)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, f"P{i}")
            self._hit.append((pt, r, i))
        p.end()

    def mouseMoveEvent(self, e):
        if not self.ex or not self.frames:
            return
        f, dims = self.frames[self.cur], self.ex.dims
        for pt, r, i in getattr(self, "_hit", []):
            if (e.position() - pt).manhattanLength() <= r * 1.4:
                lb_pos, lb_cost = f.local_best[i]
                QToolTip.showText(e.globalPosition().toPoint(),
                                  f"<b>Particle P{i}</b><br>now: {config_text(f.positions[i], dims)} "
                                  f"(cost {f.costs[i]:.4f})<br>own best: {config_text(lb_pos, dims)} ({lb_cost:.4f})", self)
                return
        g = self._geom()
        d2, rows, cols, gx, top, cw, ch = g
        c, r = int((e.position().x() - gx) // cw), int((e.position().y() - top) // ch)
        if 0 <= c < len(cols) and 0 <= r < len(rows):
            pos = ((rows[r], cols[c]) + tuple(self.ex.probe.lower[2:])) if d2 else (cols[c],)
            d = self.cost_of.get(pos)
            if d and pos in f.visited:
                QToolTip.showText(e.globalPosition().toPoint(),
                                  f"<b>{config_text(pos, dims)}</b><br>cost {d.cost:.4f}<br>"
                                  f"area {d.area:.2f} µm² · latency {d.latency:.2f} ps", self)
            else:
                QToolTip.showText(e.globalPosition().toPoint(),
                                  f"<b>{config_text(pos, dims)}</b><br>not visited by the swarm yet", self)
        else:
            QToolTip.hideText()


class ConvergenceStrip(QWidget):
    """Best cost per iteration, drawn only up to the replay's current iteration, on an
    x axis that always runs to the hard limit (so it never reveals when the run stops)."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(150)
        self.res, self.max_iter, self.upto, self.done = None, 50, 0, False

    def set_run(self, res, max_iter, stall):
        self.res, self.max_iter, self.stall, self.upto, self.done = res, max_iter, stall, 0, False
        ys = [h["gbest_cost"] for h in res.history]
        pad = (max(ys) - min(ys)) * 0.2 or 0.01
        self.ylo, self.yhi = min(ys) - pad, max(ys) + pad
        self.update()

    def set_position(self, iteration, done):
        self.upto, self.done = iteration, done
        self.update()

    def paintEvent(self, _):
        if not self.res:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m_l, m_r, m_t, m_b = 64, 18, 22, 28
        W, H = self.width(), self.height()
        X = lambda v: m_l + v / self.max_iter * (W - m_l - m_r)
        Y = lambda v: m_t + (1 - (v - self.ylo) / (self.yhi - self.ylo)) * (H - m_t - m_b)
        f = QFont()
        f.setPixelSize(11)
        p.setFont(f)
        for k in range(5):
            v = self.ylo + (self.yhi - self.ylo) * k / 4
            p.setPen(QPen(QColor("#e6e9ef"), 1))
            p.drawLine(QPointF(m_l, Y(v)), QPointF(W - m_r, Y(v)))
            p.setPen(QColor(theme.INK_2))
            p.drawText(QRectF(0, Y(v) - 8, m_l - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{v:.3f}")
        for it in range(0, self.max_iter + 1, max(1, self.max_iter // 10)):
            p.drawText(QRectF(X(it) - 15, H - m_b + 6, 30, 14), Qt.AlignmentFlag.AlignCenter, str(it))
        p.setPen(QPen(QColor(theme.MUTED), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(X(self.max_iter), m_t - 6), QPointF(X(self.max_iter), H - m_b))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(W - m_r - 220, 2, 216, 16), Qt.AlignmentFlag.AlignRight, f"hard limit: {self.max_iter} iterations")
        p.setPen(QColor(theme.INK_2))
        p.drawText(QRectF(m_l, 2, 300, 16), Qt.AlignmentFlag.AlignLeft, "best design cost so far")
        hist = [h for h in self.res.history if h["iteration"] <= self.upto]
        path = QPainterPath(QPointF(X(hist[0]["iteration"]), Y(hist[0]["gbest_cost"])))
        for h in hist[1:]:
            path.lineTo(QPointF(X(h["iteration"]), path.currentPosition().y()))
            path.lineTo(QPointF(X(h["iteration"]), Y(h["gbest_cost"])))
        p.setPen(QPen(QColor(theme.ADDER), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        prev = None
        for h in hist:
            if prev is None or h["gbest_cost"] < prev - 1e-12:
                p.setPen(QPen(QColor("#ffffff"), 2))
                p.setBrush(QColor(theme.ADDER))
                p.drawEllipse(QPointF(X(h["iteration"]), Y(h["gbest_cost"])), 4.5, 4.5)
            prev = h["gbest_cost"]
        if self.done and self.res.iterations_run > self.res.convergence_iter:
            ci, last = self.res.convergence_iter, self.res.iterations_run
            yb = Y(self.res.best.cost) - 10
            p.setPen(QPen(QColor(theme.INK_2), 1.2))
            p.drawLine(QPointF(X(ci) + 4, yb), QPointF(X(last), yb))
            p.drawLine(QPointF(X(ci) + 4, yb + 4), QPointF(X(ci) + 4, yb))
            p.drawLine(QPointF(X(last), yb + 4), QPointF(X(last), yb))
            p.drawText(QRectF(X(ci) + 8, yb - 18, 460, 16), Qt.AlignmentFlag.AlignLeft,
                       f"best found at iteration {ci}, then {last - ci} iterations without improvement → stop")
        p.end()
