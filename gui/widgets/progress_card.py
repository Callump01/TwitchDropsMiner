from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QProgressBar, QFrame,
)

from gui.widgets.animated_card import AnimatedCard
from gui.widgets.ring_progress import RingProgress
from gui.widgets.segmented_bar import SegmentedProgressBar
from gui.animations import SmoothProgressHelper
from translate import _

if TYPE_CHECKING:
    from gui.manager import GUIManager
    from inventory import TimedDrop


class ProgressCard(AnimatedCard):
    """
    Campaign and drop progress card with ring indicator and segmented bar.

    Layout:
    ┌──────────────────────────────────────────────────────┐
    │  PROGRESS                                             │
    │  Game: ...                    Campaign: ...           │
    │                                                       │
    │  ┌────────┐  ┌─────────────────────────────────────┐ │
    │  │  Ring  │  │ Current Drop                         │ │
    │  │ 120px  │  │ [reward text]                        │ │
    │  │        │  │ ████████░░░░░ 45.2%                  │ │
    │  │ 2:15   │  │ Remaining: 2:15:30                   │ │
    │  │ 45.2%  │  │ Est. done: ~3:45 PM                  │ │
    │  └────────┘  └─────────────────────────────────────┘ │
    │                                                       │
    │  Campaign: ██▓░░░░ 2/5 drops (40%)                   │
    │  ┌─┐┌─┐┌▓┐┌─┐┌─┐  Remaining: 12:30:00              │
    └──────────────────────────────────────────────────────┘

    Preserves the exact same public API as the original ProgressCard.
    """

    ALMOST_DONE_SECONDS = 10
    PROGRESS_MAX = 10000  # Used internally for QProgressBar fallback

    def __init__(self, manager: GUIManager, parent=None):
        super().__init__(parent, padding=14)
        self._manager = manager
        self._drop: TimedDrop | None = None
        self._seconds: int = 0
        self._timer_task: asyncio.Task[None] | None = None

        # Prevent the card from being squished by sibling widgets.
        # Content: title(20) + info_grid(50) + drop_row(ring 120 + margins) +
        #          separator(2) + campaign section(40) + padding(28) ≈ 290
        self.setMinimumHeight(290)

        # Section title
        title = QLabel(_("gui", "progress", "name"), self)
        title.setProperty("class", "section-title")
        self.card_layout.addWidget(title)

        # Game & Campaign info row
        info_grid = QGridLayout()
        info_grid.setSpacing(4)
        info_grid.setContentsMargins(0, 4, 0, 4)

        game_label = QLabel(_("gui", "progress", "game"), self)
        game_label.setProperty("class", "muted")
        info_grid.addWidget(game_label, 0, 0)
        self._game_name = QLabel("...", self)
        info_grid.addWidget(self._game_name, 1, 0)

        campaign_label = QLabel(_("gui", "progress", "campaign"), self)
        campaign_label.setProperty("class", "muted")
        info_grid.addWidget(campaign_label, 0, 1)
        self._campaign_name = QLabel("...", self)
        info_grid.addWidget(self._campaign_name, 1, 1)

        self.card_layout.addLayout(info_grid)

        # ---- Drop section: Ring + Details side by side ----
        drop_row = QHBoxLayout()
        drop_row.setSpacing(16)

        # Ring progress (left)
        self._ring = RingProgress(self, theme=manager._theme)
        drop_row.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignTop)

        # Drop details (right)
        drop_details = QVBoxLayout()
        drop_details.setSpacing(4)

        drop_title = QLabel(_("gui", "progress", "drop"), self)
        drop_title.setProperty("class", "muted")
        drop_details.addWidget(drop_title)

        self._drop_rewards = QLabel("...", self)
        self._drop_rewards.setProperty("class", "heading")
        self._drop_rewards.setWordWrap(True)
        drop_details.addWidget(self._drop_rewards)

        # Drop progress bar (thin, supplements the ring for at-a-glance view)
        drop_bar_row = QHBoxLayout()
        drop_bar_row.setSpacing(8)
        self._drop_bar = QProgressBar(self)
        self._drop_bar.setRange(0, self.PROGRESS_MAX)
        self._drop_bar.setValue(0)
        self._drop_bar.setTextVisible(False)
        self._drop_bar.setFixedHeight(6)
        drop_bar_row.addWidget(self._drop_bar, 1)
        self._drop_pct = QLabel("-%", self)
        self._drop_pct.setProperty("class", "muted")
        self._drop_pct.setMinimumWidth(50)
        self._drop_pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        drop_bar_row.addWidget(self._drop_pct)
        drop_details.addLayout(drop_bar_row)

        # Drop remaining time
        self._drop_remaining = QLabel("", self)
        self._drop_remaining.setProperty("class", "muted")
        drop_details.addWidget(self._drop_remaining)

        # Estimated completion time
        self._eta_label = QLabel("", self)
        self._eta_label.setProperty("class", "muted")
        drop_details.addWidget(self._eta_label)

        drop_details.addStretch(1)
        drop_row.addLayout(drop_details, 1)

        self.card_layout.addLayout(drop_row)

        # ---- Separator ----
        sep = QFrame(self)
        sep.setProperty("class", "separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        self.card_layout.addWidget(sep)

        # ---- Campaign section: segmented bar ----
        camp_header = QHBoxLayout()
        camp_prog_label = QLabel(_("gui", "progress", "campaign_progress"), self)
        camp_prog_label.setProperty("class", "muted")
        camp_header.addWidget(camp_prog_label)
        camp_header.addStretch(1)
        self._campaign_pct = QLabel("-%", self)
        camp_header.addWidget(self._campaign_pct)
        self.card_layout.addLayout(camp_header)

        self._segmented_bar = SegmentedProgressBar(self, theme=manager._theme)
        self.card_layout.addWidget(self._segmented_bar)

        # Campaign remaining (fallback thin bar + time)
        camp_bottom = QHBoxLayout()
        self._campaign_bar = QProgressBar(self)
        self._campaign_bar.setRange(0, self.PROGRESS_MAX)
        self._campaign_bar.setValue(0)
        self._campaign_bar.setTextVisible(False)
        self._campaign_bar.setFixedHeight(4)
        self._campaign_bar.setVisible(False)  # hidden; segmented bar is primary
        camp_bottom.addWidget(self._campaign_bar, 1)

        self._campaign_remaining = QLabel("", self)
        self._campaign_remaining.setProperty("class", "muted")
        self._campaign_remaining.setAlignment(Qt.AlignmentFlag.AlignRight)
        camp_bottom.addWidget(self._campaign_remaining)
        self.card_layout.addLayout(camp_bottom)

        # Smooth progress animators (for the thin progress bars)
        self._camp_anim = SmoothProgressHelper(self)
        self._camp_anim.value_changed.connect(self._campaign_bar.setValue)
        self._drop_anim = SmoothProgressHelper(self)
        self._drop_anim.value_changed.connect(self._drop_bar.setValue)

        self.display(None)

    # ---- Time handling (matches original logic exactly) ----
    def _divmod(self, minutes: int) -> tuple[int, int]:
        if self._seconds < 60 and minutes > 0:
            minutes -= 1
        hours, minutes = divmod(minutes, 60)
        return (hours, minutes)

    def _update_time(self, seconds: int | None = None) -> None:
        if seconds is not None:
            self._seconds = seconds
        drop = self._drop
        if drop is not None:
            drop_minutes = drop.remaining_minutes
            campaign_minutes = drop.campaign.remaining_minutes
        else:
            drop_minutes = 0
            campaign_minutes = 0
        dseconds = self._seconds % 60

        # Drop time
        hours, minutes = self._divmod(drop_minutes)
        time_str = f"{hours:>2}:{minutes:02}:{dseconds:02}"
        self._drop_remaining.setText(
            _("gui", "progress", "remaining").format(time=time_str)
        )
        # Update ring center text with compact time
        self._ring.set_center_text(f"{hours}:{minutes:02}" if hours else f"{minutes}:{dseconds:02}")

        # Campaign time
        hours, minutes = self._divmod(campaign_minutes)
        self._campaign_remaining.setText(
            _("gui", "progress", "remaining").format(time=f"{hours:>2}:{minutes:02}:{dseconds:02}")
        )

        # Update estimated completion time
        if drop is not None and drop_minutes > 0:
            eta = datetime.now() + timedelta(minutes=drop_minutes)
            self._eta_label.setText(f"Est. done: ~{eta.strftime('%I:%M %p')}")
            self._eta_label.setVisible(True)
        else:
            self._eta_label.setVisible(False)

    async def _timer_loop(self) -> None:
        self._update_time(60)
        while self._seconds > 0:
            await asyncio.sleep(1)
            self._seconds -= 1
            self._update_time()
        self._timer_task = None

    def start_timer(self) -> None:
        if self._timer_task is None:
            if self._drop is None or self._drop.remaining_minutes <= 0:
                self._update_time(60)
            else:
                self._timer_task = asyncio.create_task(self._timer_loop())

    def stop_timer(self) -> None:
        if self._timer_task is not None:
            self._timer_task.cancel()
            self._timer_task = None

    def minute_almost_done(self) -> bool:
        return self._timer_task is None or self._seconds <= self.ALMOST_DONE_SECONDS

    # ---- Display ----
    def display(self, drop: TimedDrop | None, *, countdown: bool = True, subone: bool = False) -> None:
        self._drop = drop
        self.stop_timer()
        if drop is None:
            self._drop_rewards.setText("...")
            self._drop_pct.setText("-%")
            self._campaign_name.setText("...")
            self._game_name.setText("...")
            self._campaign_pct.setText("-%")
            self._drop_anim.set_value_instant(0)
            self._camp_anim.set_value_instant(0)
            self._ring.set_progress(0.0, animated=False)
            self._ring.set_center_text("--:--")
            self._ring.set_sub_text("-%")
            self._segmented_bar.set_segments(0, 0.0, 1)
            self._eta_label.setVisible(False)
            self._update_time(0)
            return

        # Drop info
        self._drop_rewards.setText(drop.rewards_text())
        drop_val = int(drop.progress * self.PROGRESS_MAX)
        self._drop_anim.animate_to(drop_val)
        self._drop_pct.setText(f"{drop.progress:6.1%}")
        self._ring.set_progress(drop.progress)
        self._ring.set_sub_text(f"{drop.progress:.1%}")

        # Campaign info
        campaign = drop.campaign
        self._campaign_name.setText(campaign.name)
        self._game_name.setText(campaign.game.name)
        camp_val = int(campaign.progress * self.PROGRESS_MAX)
        self._camp_anim.animate_to(camp_val)
        self._campaign_pct.setText(
            f"{campaign.progress:6.1%} ({campaign.claimed_drops}/{campaign.total_drops})"
        )

        # Segmented bar: claimed drops + current drop progress
        self._segmented_bar.set_segments(
            campaign.claimed_drops, drop.progress, campaign.total_drops
        )

        if countdown:
            self.start_timer()
        elif subone:
            self._update_time(0)
        else:
            self._update_time(60)
