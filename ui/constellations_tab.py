"""
ui/constellations_tab.py — Ciel › Constellations: the chart of each of the 88 (v4.24).

A mixin of the main window (gui.AstroApp): the constellation chosen in a list
(the names in the interface's language), its chart as in the sky atlases
(constellation_chart.py: the official outline, the figure, the stars and their
Greek letters, the deep-sky objects, the neighbours), its facts for the place
(area, the month it is highest at 10 pm, whether it rises here, its brightest
stars and finest objects), and its sheet to print (PDF, A4).
"""
import html
import unicodedata

import constellation_chart
from star_catalog import CATALOG
from ui import common
from ui.common import *  # noqa: F401,F403


_CO_PHONE_HEIGHT = 300           # px: the chart's least height on a phone
_QT_MAX_SIZE = 16777215          # QWIDGETSIZE_MAX


def _sort_key(name):
    """Alphabetical order without the accents: Écu de Sobieski among the E."""
    plain = unicodedata.normalize("NFKD", name)
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


class ConstellationSpace:
    def _build_constellations_tab(self):
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._co_combo = QComboBox()
        # no wider than a phone for the longest names (Kleine Männliche Wasserschlange)
        self._co_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._co_combo.setMinimumContentsLength(14)
        names = self._co_names()
        for key in sorted(names, key=lambda k: _sort_key(names[k])):
            self._co_combo.addItem(f"{names[key]} ({key})", key)
        self._co_combo.setCurrentIndex(max(0, self._co_combo.findData(prefs.get("constellation") or "Ori")))
        self._co_combo.currentIndexChanged.connect(lambda _i: self._co_changed())
        bar.addWidget(InputField(t("constellation_chart.choose"), self._co_combo), stretch=1)
        self._co_pdf = _button(t("constellation_chart.pdf"), "export", compact=True)
        self._co_pdf.setToolTip(t("constellation_chart.pdf_tip"))
        self._co_pdf.clicked.connect(lambda _c=False: self._save_constellation_sheet())
        bar.addWidget(self._co_pdf, alignment=Qt.AlignmentFlag.AlignBottom)
        inner, self.fig_co, self.canvas_co = self._chart_page("constellation", toolbar=bar,
                                                              hint=t("constellation_chart.hint"))
        self._co_facts = _label("", "corps", wrap=True)
        self._co_facts.setTextFormat(Qt.TextFormat.RichText)
        self._co_facts.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = inner.layout()
        layout.insertWidget(layout.count() - 1, self._co_facts)          # under the chart, above the hint
        self._co_square = False
        self.canvas_co.mpl_connect("resize_event", lambda _e: self._co_resized())
        page = QScrollArea()                                             # a phone: the chart, then the facts
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        page.setWidget(inner)
        self._chart_tabs[page] = "constellation"
        self._compact_hooks.append(self._co_compact)
        self._constellation_page = page
        self._dirty.add("constellation")
        self._add_page(page, t("tabs.constellations"))

    def _co_compact(self, compact):
        """On a phone: the PDF button as an icon, and the chart square, as tall as it is wide (the page
        scrolls to the facts)."""
        self._co_pdf.setText("" if compact else t("constellation_chart.pdf"))
        self._co_square = compact
        if compact:
            self._co_fit_height()
        else:
            self.canvas_co.setMinimumHeight(0)
            self.canvas_co.setMaximumHeight(_QT_MAX_SIZE)

    def _co_fit_height(self):
        side = max(_CO_PHONE_HEIGHT, self.canvas_co.width())
        if self.canvas_co.minimumHeight() != side or self.canvas_co.maximumHeight() != side:
            self.canvas_co.setFixedHeight(side)

    def _co_resized(self):
        """The chart changed size: square on a phone; its labels measured again
        (constellation_chart.declutter)."""
        if self._co_square:
            self._co_fit_height()
        if self.fig_co.axes:
            constellation_chart.declutter(self.fig_co.axes[0])

    def _co_names(self):
        return {key: t(f"constellations.{key}") for key in constellation_chart.outlines()}

    def _co_key(self):
        return self._co_combo.currentData() or "Ori"

    def _co_changed(self):
        prefs.set("constellation", self._co_key())
        self._dirty.add("constellation")
        self._draw_visible_chart()

    def _draw_constellation(self):
        """The chart of the constellation chosen, in the theme's colours, and its facts."""
        key = self._co_key()
        scene = constellation_chart.chart(key, CATALOG, charts.constellation_figures(), planner.deep_sky_catalog())
        fig = self.fig_co
        fig.clear()
        fig.set_layout_engine("none")
        fig.patch.set_facecolor(Config.CIEL_000)
        ax = fig.add_axes((0.01, 0.01, 0.98, 0.98))
        colors = {"background": Config.CIEL_000, "ink": Config.ENCRE, "soft": Config.ENCRE_ATTENUEE,
                  "faint": mix(Config.ENCRE_ATTENUEE, Config.CIEL_000, 0.75), "grid": Config.CIEL_200,
                  "outline": Config.OR, "deep": Config.LUNE}
        constellation_chart.draw(ax, scene, self._co_names(), colors)
        self._co_scene = scene
        self.canvas_co.draw_idle()
        self._show_co_facts(key)

    def _show_co_facts(self, key):
        info = constellation_chart.facts(key, self._lat if self._lat is not None else 45.0, CATALOG,
                                         planner.deep_sky_catalog())
        name = self._co_names()[key]
        parts = [f"<b>{html.escape(name)}</b> · {html.escape(constellation_chart.fact_line(key, info))}"]
        if info["stars"]:
            parts.append(f"<b>{html.escape(t('constellation_chart.stars'))}</b> : "
                         + " ; ".join(html.escape(constellation_chart.star_line(row)) for row in info["stars"]))
        if info["objects"]:
            parts.append(f"<b>{html.escape(t('constellation_chart.objects'))}</b> : "
                         + " ; ".join(html.escape(constellation_chart.object_line(row)) for row in info["objects"]))
        self._co_facts.setText("<br>".join(parts))

    def _save_constellation_sheet(self, path=None):
        """Asks where to save, then writes the constellation's A4 sheet (PDF)."""
        key = self._co_key()
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, t("constellation_chart.save_title"),
                                                  f"{_sort_key(self._co_names()[key]).replace(' ', '-')}.pdf",
                                                  "PDF (*.pdf)")
            if not path:
                return None
        place = getattr(self, "location_name", "") or ""
        coords = (f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}" if self._lat is not None else "")
        try:
            constellation_chart.sheet(path, key, self._lat if self._lat is not None else 45.0,
                                      " · ".join(x for x in (place, coords) if x), CATALOG,
                                      charts.constellation_figures(), planner.deep_sky_catalog())
        except (OSError, ValueError, RuntimeError) as exc:
            common.QMessageBox.warning(self, t("constellation_chart.save_title"), str(exc))
            return None
        self.statusBar().showMessage(tf("constellation_chart.saved", path=path), 8000)
        return path
