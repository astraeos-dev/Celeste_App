"""
ui/journal_tab.py — Observer › Journal: the observation log (journal.py).

A mixin of the main window (gui.AstroApp): the table of the observations,
newest first; a window to add or change one (date, target, place, instrument,
seeing, transparency, notes, and the quality of the night computed by
Céleste); delete; export as CSV. An observation is also added from the
Targets list (right click).
"""
from ui import common
from ui.common import *  # noqa: F401,F403

import journal

_JOURNAL_COLUMNS = ("date", "target", "place", "instrument", "seeing", "quality", "notes")
_ID_ROLE = Qt.ItemDataRole.UserRole + 7


class JournalSpace:
    # ── The page ──────────────────────────────────────────────────────────

    def _build_journal_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._journal_add_btn = _button(t("journal.add"), "note")
        self._journal_add_btn.setToolTip(t("journal.add_tip"))
        self._journal_add_btn.clicked.connect(lambda _=False: self._journal_open())
        bar.addWidget(self._journal_add_btn)
        self._journal_edit_btn = _icon_button("edit", t("journal.edit"))
        self._journal_edit_btn.clicked.connect(self._journal_edit_selected)
        self._journal_delete_btn = _icon_button("delete", t("journal.delete"))
        self._journal_delete_btn.clicked.connect(self._journal_delete_selected)
        for button in (self._journal_edit_btn, self._journal_delete_btn):
            button.setEnabled(False)
            bar.addWidget(button)
        self._journal_count = _label("", "legende", tone="attenuee")
        bar.addWidget(self._journal_count, stretch=1)
        self._journal_export_btn = _button(t("journal.export"), "export")
        self._journal_export_btn.setToolTip(t("journal.export_tip"))
        self._journal_export_btn.clicked.connect(self._journal_export)
        bar.addWidget(self._journal_export_btn)
        lay.addLayout(bar)

        table = QTableWidget(0, len(_JOURNAL_COLUMNS))
        table.setHorizontalHeaderLabels([t(f"journal.col_{key}") for key in _JOURNAL_COLUMNS])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        header = table.horizontalHeader()
        for col, key in enumerate(_JOURNAL_COLUMNS):
            if key in ("place", "instrument"):                 # long texts: a set width, elided
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(col, 150)
            elif key == "notes":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.itemSelectionChanged.connect(self._journal_selection_changed)
        table.itemDoubleClicked.connect(lambda _item: self._journal_edit_selected())
        self._journal_table = table
        lay.addWidget(table, stretch=1)
        self._journal_empty = _label(t("journal.empty"), "corps", tone="attenuee", wrap=True)
        lay.addWidget(self._journal_empty)
        self._journal_page = page
        self._add_page(page, t("tabs.journal"))
        self._refresh_journal()

    def _refresh_journal(self):
        """The table from the journal on disk, newest first."""
        entries = journal.load()
        self._journal_entries = {e["id"]: e for e in entries}
        table = self._journal_table
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for col, key in enumerate(_JOURNAL_COLUMNS):
                item = QTableWidgetItem(self._journal_cell(entry, key))
                item.setData(_ID_ROLE, entry["id"])
                if key == "notes":
                    item.setToolTip(entry["notes"])
                table.setItem(row, col, item)
        self._journal_count.setText(tf(_plural_key("journal.count", len(entries)), n=len(entries)))
        self._journal_empty.setVisible(not entries)
        table.setVisible(bool(entries))
        self._journal_selection_changed()

    def _journal_cell(self, entry, key):
        if key == "date":
            try:
                when = datetime.fromisoformat(entry["date"])
            except ValueError:
                return entry["date"]
            local = self._local(when)
            return f"{local:%d/%m/%Y} {self._fmt_clock(local)}"
        if key == "seeing":
            parts = [f"{entry[k]}/5" if entry[k] else "—" for k in ("seeing", "transparency")]
            return " · ".join(parts)
        if key == "quality":
            return "—" if entry["quality"] is None else f"{entry['quality']}/100"
        if key == "notes":
            return entry["notes"].replace("\n", " ")
        return entry[key] or "—"

    def _journal_selected_id(self):
        items = self._journal_table.selectedItems()
        return items[0].data(_ID_ROLE) if items else None

    def _journal_selection_changed(self):
        selected = self._journal_selected_id() is not None
        self._journal_edit_btn.setEnabled(selected)
        self._journal_delete_btn.setEnabled(selected)

    # ── Add, change, delete, export ───────────────────────────────────────

    def _journal_open(self, entry=None, target=""):
        """The window of an observation: new (with *target*), or *entry* to change."""
        dlg = self._journal_dialog(entry, target)
        dlg.open()
        return dlg

    def _journal_edit_selected(self):
        entry = self._journal_entries.get(self._journal_selected_id())
        if entry is not None:
            self._journal_open(entry)

    def _journal_dialog(self, entry=None, target=""):
        """The window (not shown): its fields, and save() that writes the entry."""
        new = entry is None
        dlg = QDialog(self)
        dlg.setWindowTitle(t("journal.new_title" if new else "journal.edit_title"))
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)

        when = QDateTimeEdit()
        when.setDisplayFormat("dd/MM/yyyy HH:mm")
        when.setCalendarPopup(True)
        if new:
            local = self._local(datetime.now(timezone.utc).replace(tzinfo=None))
        else:
            try:
                local = self._local(datetime.fromisoformat(entry["date"]))
            except ValueError:
                local = self._local(datetime.now(timezone.utc).replace(tzinfo=None))
        when.setDateTime(QDateTime(QDate(local.year, local.month, local.day),
                                   QTime(local.hour, local.minute)))
        lay.addWidget(InputField(t("journal.col_date"), when, hint=t("journal.date_hint")))

        target_edit = QLineEdit(entry["target"] if entry else target)
        target_edit.setPlaceholderText(t("journal.target_placeholder"))
        lay.addWidget(InputField(t("journal.col_target"), target_edit))

        place_edit = QLineEdit(entry["place"] if entry else (self.location_name or ""))
        lay.addWidget(InputField(t("journal.col_place"), place_edit))

        instrument_edit = QLineEdit(entry["instrument"] if entry else (prefs.get("journal_instrument") or ""))
        instrument_edit.setPlaceholderText(t("journal.instrument_placeholder"))
        lay.addWidget(InputField(t("journal.col_instrument"), instrument_edit))

        row = QHBoxLayout()
        row.setSpacing(16)
        combos = {}
        for key in ("seeing", "transparency"):
            combo = QComboBox()
            combo.addItem("—", 0)
            for n in range(1, 6):
                combo.addItem(tf("journal.scale_item", n=n, label=t(f"journal.scale_{n}")), n)
            value = entry[key] if entry else 0
            combo.setCurrentIndex(max(0, combo.findData(value or 0)))
            combos[key] = combo
            row.addWidget(InputField(t(f"journal.{key}"), combo, hint=t(f"journal.{key}_hint")),
                          stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(row)

        quality = entry["quality"] if entry else self._journal_night_score()
        quality_label = _label(tf("journal.quality", score=quality) if quality is not None
                               else t("journal.quality_none"), "legende", tone="attenuee", wrap=True)
        lay.addWidget(quality_label)

        notes_edit = QPlainTextEdit(entry["notes"] if entry else "")
        notes_edit.setPlaceholderText(t("journal.notes_placeholder"))
        notes_edit.setMinimumHeight(110)
        lay.addWidget(_label(t("journal.col_notes"), "label"))
        lay.addWidget(notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(buttons)

        def save():
            local_dt = when.dateTime().toPython() if hasattr(when.dateTime(), "toPython") \
                else when.dateTime().toPyDateTime()
            utc = self._to_utc(local_dt)
            values = {"date": utc, "target": target_edit.text(), "place": place_edit.text(),
                      "lat": entry["lat"] if entry else self._lat, "lon": entry["lon"] if entry else self._lon,
                      "instrument": instrument_edit.text(), "notes": notes_edit.toPlainText(),
                      "seeing": combos["seeing"].currentData(),
                      "transparency": combos["transparency"].currentData(), "quality": quality}
            if not values["target"].strip():
                target_edit.setFocus()
                return None
            if new:
                kept = journal.add(values)
            else:
                values["id"] = entry["id"]
                kept = journal.update(values)
            prefs.set("journal_instrument", instrument_edit.text().strip())
            self._refresh_journal()
            self.statusBar().showMessage(t("journal.saved"), 4000)
            dlg.accept()
            return kept

        buttons.accepted.connect(save)
        buttons.rejected.connect(dlg.reject)
        dlg.fields = {"date": when, "target": target_edit, "place": place_edit,
                      "instrument": instrument_edit, "notes": notes_edit, **combos}
        dlg.save = save
        self._journal_dlg = dlg
        return dlg

    def _journal_night_score(self):
        """The quality of the night shown in Tonight, or None without a dark night."""
        q = getattr(self, "_night_quality", None)
        return q["score"] if q and q["rating"] != "no_night" else None

    def _to_utc(self, local_dt):
        """A naive local datetime of the place → naive UT."""
        zone = self._zone
        aware = local_dt.replace(tzinfo=zone) if hasattr(zone, "utcoffset") else local_dt
        return aware.astimezone(timezone.utc).replace(tzinfo=None)

    def _journal_delete_selected(self):
        entry_id = self._journal_selected_id()
        entry = self._journal_entries.get(entry_id)
        if entry is None:
            return
        answer = common.QMessageBox.question(self, t("journal.delete"),
                                             tf("journal.delete_confirm", target=entry["target"]))
        if answer == common.QMessageBox.StandardButton.Yes:
            journal.delete(entry_id)
            self._refresh_journal()

    def _journal_export(self):
        entries = journal.load()
        if not entries:
            self.statusBar().showMessage(t("journal.empty"), 4000)
            return
        path, _ = QFileDialog.getSaveFileName(self, t("journal.export"), "journal-celeste.csv", "CSV (*.csv)")
        if not path:
            return
        headers = {key: t(f"journal.csv_{key}") for key in journal.FIELDS}
        journal.export_csv(entries, path, headers)
        self.statusBar().showMessage(tf("journal.exported", path=path), 6000)
