from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QPushButton, QFrame, QProgressBar, QGridLayout,
    QSizePolicy,
)

from gui.widgets.animated_card import AnimatedCard
from gui.widgets.toggle_switch import ToggleSwitch
from gui.widgets.skeleton import SkeletonCard
from gui.animations import fade_in, fade_out, StylePulseAnimator
from translate import _
from constants import PriorityMode

if TYPE_CHECKING:
    from gui.manager import GUIManager
    from inventory import DropsCampaign, TimedDrop
    from settings import Settings
    from cache import ImageCache


def _make_status_pill(text: str, bg_color: str, parent: QWidget) -> QLabel:
    """Create a small colored pill/chip label for campaign status."""
    pill = QLabel(text, parent)
    pill.setStyleSheet(
        f"background: {bg_color}; color: white; border-radius: 10px;"
        f" padding: 2px 10px; font-size: 11px; font-weight: 600;"
    )
    pill.setFixedHeight(20)
    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return pill


class _CampaignCard(AnimatedCard):
    """A single campaign card in the inventory grid.

    Shadow is disabled to prevent Qt rendering crashes when many cards
    are created off-screen and then made visible at once via tab switch.
    """

    MIN_CARD_WIDTH = 420

    def __init__(self, campaign: DropsCampaign, parent=None):
        super().__init__(parent, padding=12, shadow=False)
        self.campaign = campaign
        self.setMinimumWidth(self.MIN_CARD_WIDTH)


class InventoryTab(QWidget):
    """
    Inventory overview with filter bar and scrollable campaign card grid.

    Each campaign is displayed as a card with image, status, dates,
    linking status, allowed channels, and drop progress.
    """

    def __init__(self, manager: GUIManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._cache: ImageCache = manager._cache
        self._settings: Settings = manager._twitch.settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Filter bar
        filter_card = AnimatedCard(self, padding=10)
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        filter_title = QLabel(_("gui", "inventory", "filter", "show"), self)
        filter_title.setProperty("class", "section-title")
        filter_layout.addWidget(filter_title)

        self._filters: dict[str, ToggleSwitch] = {}
        filter_defaults = {
            "not_linked": self._settings.priority_mode is PriorityMode.PRIORITY_ONLY,
            "upcoming": True,
            "expired": False,
            "excluded": False,
            "finished": False,
        }
        filter_keys = ["not_linked", "upcoming", "expired", "excluded", "finished"]
        for key in filter_keys:
            toggle = ToggleSwitch(self, checked=filter_defaults.get(key, False), theme=self._manager._theme)
            label = QLabel(_("gui", "inventory", "filter", key), self)
            filter_layout.addWidget(toggle)
            filter_layout.addWidget(label)
            self._filters[key] = toggle

        filter_layout.addStretch(1)

        refresh_btn = QPushButton(_("gui", "inventory", "filter", "refresh"), self)
        refresh_btn.clicked.connect(self.refresh)
        filter_layout.addWidget(refresh_btn)

        filter_card.card_layout.addLayout(filter_layout)
        layout.addWidget(filter_card)

        # Scroll area for campaigns
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(12)
        self._container_layout.addStretch(1)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        # Empty state overlay (shown when no campaigns are visible)
        self._empty_widget = QWidget(self._container)
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)

        empty_icon = QLabel("\U0001F4E6", self._empty_widget)
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setStyleSheet("font-size: 48px; background: transparent;")
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel(_("gui", "inventory", "empty"), self._empty_widget)
        empty_title.setProperty("class", "heading")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        empty_hint = QLabel(_("gui", "inventory", "empty_hint"), self._empty_widget)
        empty_hint.setProperty("class", "muted")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setWordWrap(True)
        empty_layout.addWidget(empty_hint)

        empty_action = QPushButton(_("gui", "inventory", "filter", "refresh"), self._empty_widget)
        empty_action.setProperty("class", "accent")
        empty_action.setFixedWidth(220)
        empty_action.clicked.connect(self.refresh)
        empty_layout.addWidget(empty_action, 0, Qt.AlignmentFlag.AlignCenter)

        self._container_layout.insertWidget(0, self._empty_widget)

        self._campaigns: dict[DropsCampaign, _CampaignCard] = {}
        self._drop_labels: dict[str, QLabel] = {}
        self._pulse_animators: dict[DropsCampaign, StylePulseAnimator] = {}
        self._skeletons: list[SkeletonCard] = []

    def _update_empty_state(self) -> None:
        """Show or hide the empty state based on campaign cards.

        The empty state is hidden if any campaigns exist in the dict
        (regardless of filter visibility) or if skeleton placeholders
        are being shown.
        """
        has_campaigns = bool(self._campaigns)
        has_skeletons = bool(self._skeletons)
        self._empty_widget.setVisible(not has_campaigns and not has_skeletons)

    def _update_visibility(self, campaign: DropsCampaign) -> None:
        card = self._campaigns.get(campaign)
        if card is None:
            return
        not_linked = self._filters["not_linked"].isChecked()
        expired = self._filters["expired"].isChecked()
        upcoming = self._filters["upcoming"].isChecked()
        excluded = self._filters["excluded"].isChecked()
        finished = self._filters["finished"].isChecked()
        priority_only = self._settings.priority_mode is PriorityMode.PRIORITY_ONLY

        show = (
            campaign.required_minutes > 0
            and (not_linked or campaign.eligible)
            and (campaign.active or upcoming and campaign.upcoming or expired and campaign.expired)
            and (
                excluded or (
                    campaign.game.name not in self._settings.exclude
                    and not priority_only or campaign.game.name in self._settings.priority
                )
            )
            and (finished or not campaign.finished)
        )
        card.setVisible(show)

    def get_status(self, campaign: DropsCampaign) -> tuple[str, str]:
        """Return (status_text, status_color) for a campaign."""
        palette = self._manager._theme.palette
        if campaign.active:
            return (_("gui", "inventory", "status", "active"), palette.success)
        elif campaign.upcoming:
            return (_("gui", "inventory", "status", "upcoming"), palette.warning)
        else:
            return (_("gui", "inventory", "status", "expired"), palette.error)

    def refresh(self) -> None:
        for campaign, card in self._campaigns.items():
            status_text, status_color = self.get_status(campaign)
            status_label = card.findChild(QLabel, "status_label")
            if status_label is not None:
                # Update pill styling
                status_label.setText(status_text)
                status_label.setStyleSheet(
                    f"background: {status_color}; color: white; border-radius: 10px;"
                    f" padding: 2px 10px; font-size: 11px; font-weight: 600;"
                )
            self._update_visibility(campaign)
        self._update_empty_state()

    async def add_campaign(self, campaign: DropsCampaign) -> None:
        # Clear skeleton placeholders on first real campaign
        if self._skeletons:
            self._clear_skeletons()

        card = _CampaignCard(campaign, self._container)
        card_layout = card.card_layout
        card_layout.setSpacing(8)

        # Main horizontal layout: [image | info | separator | drops]
        main_h = QHBoxLayout()
        main_h.setSpacing(12)

        # Campaign image placeholder (will be filled async)
        palette = self._manager._theme.palette
        img_label = QLabel(card)
        img_label.setFixedSize(108, 144)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet(
            f"background: {palette.border}; border-radius: 6px;"
        )
        # Pulse animation while loading (stylesheet-based, avoids QPainter conflicts)
        pulse = StylePulseAnimator(img_label, base_color=palette.border)
        pulse.start()
        self._pulse_animators[campaign] = pulse
        main_h.addWidget(img_label)

        # Info column
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        # Name
        name_label = QLabel(campaign.name, card)
        name_label.setProperty("class", "heading")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        # Status pill
        status_text, status_color = self.get_status(campaign)
        status_pill = _make_status_pill(status_text, status_color, card)
        status_pill.setObjectName("status_label")
        info_layout.addWidget(status_pill, 0, Qt.AlignmentFlag.AlignLeft)

        # Dates
        ends_text = _("gui", "inventory", "ends").format(
            time=campaign.ends_at.astimezone().replace(microsecond=0, tzinfo=None)
        )
        date_label = QLabel(ends_text, card)
        date_label.setProperty("class", "muted")
        info_layout.addWidget(date_label)

        # Link status
        if campaign.eligible:
            link_text = _("gui", "inventory", "status", "linked")
            link_color = palette.success
        else:
            link_text = _("gui", "inventory", "status", "not_linked")
            link_color = palette.error
        link_label = QLabel(link_text, card)
        link_label.setStyleSheet(f"color: {link_color}; background: transparent;")
        link_label.setCursor(Qt.CursorShape.PointingHandCursor)
        link_label.mousePressEvent = lambda e, url=campaign.link_url: __import__("utils").webopen(url)
        info_layout.addWidget(link_label)

        # Allowed channels
        acl = campaign.allowed_channels
        if acl:
            if len(acl) <= 5:
                allowed_text = '\n'.join(ch.name for ch in acl)
            else:
                allowed_text = '\n'.join(ch.name for ch in acl[:4])
                allowed_text += f"\n{_('gui', 'inventory', 'and_more').format(amount=len(acl) - 4)}"
        else:
            allowed_text = _("gui", "inventory", "all_channels")
        channels_label = QLabel(
            f"{_('gui', 'inventory', 'allowed_channels')}\n{allowed_text}", card
        )
        channels_label.setProperty("class", "muted")
        channels_label.setWordWrap(True)
        info_layout.addWidget(channels_label)
        info_layout.addStretch(1)

        main_h.addLayout(info_layout, 1)

        # Vertical separator
        sep = QFrame(card)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {palette.border};")
        main_h.addWidget(sep)

        # Drops grid
        drops_widget = QWidget(card)
        drops_layout = QHBoxLayout(drops_widget)
        drops_layout.setSpacing(12)
        drops_layout.setContentsMargins(0, 0, 0, 0)

        # Must save card reference before await
        self._campaigns[campaign] = card

        # Insert card into container (before the stretch)
        idx = self._container_layout.count() - 1  # before the stretch
        self._container_layout.insertWidget(idx, card)

        # Load images asynchronously
        try:
            campaign_image = await self._cache.get(campaign.image_url, size=(108, 144))
            if campaign_image is not None:
                img_label.setPixmap(campaign_image)
                img_label.setStyleSheet("border-radius: 6px;")
        except Exception:
            pass
        # Stop pulse animation regardless of success/failure
        pulse_anim = self._pulse_animators.pop(campaign, None)
        if pulse_anim is not None:
            pulse_anim.stop()

        for drop in campaign.drops:
            drop_frame = QWidget(drops_widget)
            drop_vlayout = QVBoxLayout(drop_frame)
            drop_vlayout.setContentsMargins(4, 4, 4, 4)
            drop_vlayout.setSpacing(4)

            # Benefit images + names
            try:
                benefit_images = await asyncio.gather(
                    *(self._cache.get(b.image_url, (64, 64)) for b in drop.benefits)
                )
            except Exception:
                benefit_images = [None] * len(drop.benefits)

            for benefit, bimg in zip(drop.benefits, benefit_images):
                blabel = QLabel(drop_frame)
                blabel.setFixedSize(64, 64)
                blabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if bimg is not None:
                    blabel.setPixmap(bimg)
                    # Claimed overlay: dim with checkmark
                    if drop.is_claimed:
                        blabel.setStyleSheet(
                            "border-radius: 4px; background: transparent;"
                        )
                        # Overlay a semi-transparent check
                        overlay = QLabel("\u2714", blabel)
                        overlay.setFixedSize(64, 64)
                        overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        overlay.setStyleSheet(
                            f"background: rgba(0, 0, 0, 0.5); color: {palette.success};"
                            f" font-size: 28px; border-radius: 4px;"
                        )
                else:
                    # Fallback placeholder for failed image loads
                    blabel.setText("?")
                    blabel.setStyleSheet(
                        f"background: {palette.border}; border-radius: 4px;"
                        f" color: {palette.foreground_muted}; font-size: 20px;"
                    )
                drop_vlayout.addWidget(blabel)
                bname = QLabel(benefit.name, drop_frame)
                bname.setAlignment(Qt.AlignmentFlag.AlignCenter)
                bname.setWordWrap(True)
                bname.setMaximumWidth(120)
                drop_vlayout.addWidget(bname)

            # Mini progress bar (4px height)
            mini_bar = QProgressBar(drop_frame)
            mini_bar.setRange(0, 1000)
            mini_bar.setTextVisible(False)
            mini_bar.setFixedHeight(4)
            mini_bar.setMaximumWidth(120)
            if drop.is_claimed:
                mini_bar.setValue(1000)
            elif drop.progress > 0:
                mini_bar.setValue(int(drop.progress * 1000))
            else:
                mini_bar.setValue(0)
            drop_vlayout.addWidget(mini_bar)

            # Progress label (compact text below the bar)
            progress_label = QLabel(drop_frame)
            progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._update_progress(drop, progress_label)
            self._drop_labels[drop.id] = progress_label
            drop_vlayout.addWidget(progress_label)
            drop_vlayout.addStretch(1)

            drops_layout.addWidget(drop_frame)

        main_h.addWidget(drops_widget, 2)
        card_layout.addLayout(main_h)

        # Animate card in
        fade_in(card, duration=300)
        self._update_visibility(campaign)
        self._update_empty_state()

    def _update_progress(self, drop, label: QLabel) -> None:
        palette = self._manager._theme.palette
        progress_text: str
        color: str = ""
        if drop.is_claimed:
            color = palette.success
            progress_text = _("gui", "inventory", "status", "claimed")
        elif drop.can_claim:
            color = palette.warning
            progress_text = _("gui", "inventory", "status", "ready_to_claim")
        elif drop.current_minutes or drop.can_earn():
            progress_text = _("gui", "inventory", "percent_progress").format(
                percent=f"{drop.progress:3.1%}",
                minutes=drop.required_minutes,
            )
            if drop.ends_at < drop.campaign.ends_at:
                progress_text += '\n' + _("gui", "inventory", "ends").format(
                    time=drop.ends_at.astimezone().replace(microsecond=0, tzinfo=None)
                )
        else:
            if drop.required_minutes > 0:
                progress_text = _("gui", "inventory", "minutes_progress").format(
                    minutes=drop.required_minutes
                )
            else:
                progress_text = ''
            if datetime.now(timezone.utc) < drop.starts_at > drop.campaign.starts_at:
                progress_text += '\n' + _("gui", "inventory", "starts").format(
                    time=drop.starts_at.astimezone().replace(microsecond=0, tzinfo=None)
                )
            elif drop.ends_at < drop.campaign.ends_at:
                progress_text += '\n' + _("gui", "inventory", "ends").format(
                    time=drop.ends_at.astimezone().replace(microsecond=0, tzinfo=None)
                )
        style = f"color: {color}; background: transparent;" if color else "background: transparent;"
        label.setStyleSheet(style)
        label.setText(progress_text)

    def update_drop(self, drop) -> None:
        label = self._drop_labels.get(drop.id)
        if label is not None:
            self._update_progress(drop, label)

    def remove_campaign(self, campaign) -> None:
        """Remove a specific campaign card from the inventory display."""
        card = self._campaigns.pop(campaign, None)
        if card is not None:
            # Clean up drop label references
            for drop in campaign.drops:
                self._drop_labels.pop(drop.id, None)
            # Clean up pulse animator
            pulse = self._pulse_animators.pop(campaign, None)
            if pulse is not None:
                pulse.stop()
            # Animate out and remove
            fade_out(card, duration=200)
            card.setParent(None)
            card.deleteLater()
            self._update_empty_state()

    def show_loading(self) -> None:
        """Show skeleton placeholder cards while inventory is loading."""
        self._clear_skeletons()
        self._empty_widget.setVisible(False)
        for _ in range(4):
            skeleton = SkeletonCard(self._container, theme=self._manager._theme)
            self._skeletons.append(skeleton)
            idx = self._container_layout.count() - 1  # before the stretch
            self._container_layout.insertWidget(idx, skeleton)

    def _clear_skeletons(self) -> None:
        for s in self._skeletons:
            s.stop()
            s.setParent(None)
            s.deleteLater()
        self._skeletons.clear()

    def clear(self) -> None:
        # Stop all pulse animations
        for pulse in self._pulse_animators.values():
            pulse.stop()
        self._pulse_animators.clear()
        self._clear_skeletons()
        # Remove all campaign cards
        for card in self._campaigns.values():
            card.setParent(None)
            card.deleteLater()
        self._campaigns.clear()
        self._drop_labels.clear()
        self._update_empty_state()
