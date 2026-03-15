from __future__ import annotations

import re
import math
import logging
from enum import Enum
from itertools import chain
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from functools import cached_property
from datetime import datetime, timedelta, timezone

from translate import _
from channel import Channel
from utils import timestamp, Game
from exceptions import GQLException
from constants import GQL_OPERATIONS, MAX_EXTRA_MINUTES, URLType, State

if TYPE_CHECKING:
    from collections import abc

    from twitch import Twitch
    from constants import JsonType


logger = logging.getLogger("TwitchDrops")
DIMS_PATTERN = re.compile(r'-\d+x\d+(?=\.(?:jpg|png|gif)$)', re.I)


def remove_dimensions(url: URLType) -> URLType:
    return URLType(DIMS_PATTERN.sub('', url))


@dataclass
class InventoryDiff:
    """
    Captures the result of diffing new API data against existing campaign state.
    Returned by fetch_inventory() so downstream states can short-circuit when nothing changed.
    """
    added: list[DropsCampaign] = field(default_factory=list)
    removed: list[DropsCampaign] = field(default_factory=list)
    updated: list[DropsCampaign] = field(default_factory=list)
    unchanged: list[DropsCampaign] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.updated)


class BenefitType(Enum):
    UNKNOWN = "UNKNOWN"
    BADGE = "BADGE"
    EMOTE = "EMOTE"
    DIRECT_ENTITLEMENT = "DIRECT_ENTITLEMENT"

    def is_badge_or_emote(self) -> bool:
        return self in (BenefitType.BADGE, BenefitType.EMOTE)


class Benefit:
    __slots__ = ("id", "name", "type", "image_url")

    def __init__(self, data: JsonType):
        benefit_data: JsonType = data["benefit"]
        self.id: str = benefit_data["id"]
        self.name: str = benefit_data["name"]
        self.type: BenefitType = (
            BenefitType(benefit_data["distributionType"])
            if benefit_data["distributionType"] in BenefitType.__members__.keys()
            else BenefitType.UNKNOWN
        )
        self.image_url: URLType = benefit_data["imageAssetURL"]


class BaseDrop:
    def __init__(
        self, campaign: DropsCampaign, data: JsonType, claimed_benefits: dict[str, datetime]
    ):
        self._twitch: Twitch = campaign._twitch
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.campaign: DropsCampaign = campaign
        self.benefits: list[Benefit] = [Benefit(b) for b in (data["benefitEdges"] or [])]
        self.starts_at: datetime = timestamp(data["startAt"])
        self.ends_at: datetime = timestamp(data["endAt"])
        self.claim_id: str | None = None
        self.is_claimed: bool = False
        if "self" in data:
            self.claim_id = data["self"]["dropInstanceID"]
            self.is_claimed = data["self"]["isClaimed"]
        elif (
            # If there's no self edge available, we can use claimed_benefits to determine
            # (with pretty good certainty) if this drop has been claimed or not.
            # To do this, we check if the benefitEdges appear in claimed_benefits, and then
            # deref their "lastAwardedAt" timestamps into a list to check against.
            # If the benefits were claimed while the drop was active,
            # the drop has been claimed too.
            (
                dts := [
                    claimed_benefits[bid]
                    for benefit in self.benefits
                    if (bid := benefit.id) in claimed_benefits
                ]
            )
            and all(self.starts_at <= dt < self.ends_at for dt in dts)
        ):
            self.is_claimed = True
        self.precondition_drops: list[str] = [d["id"] for d in (data["preconditionDrops"] or [])]

    def __repr__(self) -> str:
        if self.is_claimed:
            additional = ", claimed=True"
        elif self.can_earn():
            additional = ", can_earn=True"
        else:
            additional = ''
        return f"Drop({self.rewards_text()}{additional})"

    @property
    def preconditions_met(self) -> bool:
        campaign = self.campaign
        return all(campaign.timed_drops[pid].is_claimed for pid in self.precondition_drops)

    def _infer_claimed(self, claimed_benefits: dict[str, datetime]) -> bool:
        """
        Check if this drop's benefits were claimed based on benefit timestamps.
        Returns True if all benefits appear in claimed_benefits with timestamps
        within this drop's active window.
        """
        dts = [
            claimed_benefits[bid]
            for benefit in self.benefits
            if (bid := benefit.id) in claimed_benefits
        ]
        return bool(dts) and all(self.starts_at <= dt < self.ends_at for dt in dts)

    def _on_state_changed(self) -> None:
        raise NotImplementedError

    def _base_earn_conditions(self) -> bool:
        # define when a drop can be earned or not
        return (
            self.preconditions_met  # preconditions are met
            and not self.is_claimed  # isn't already claimed
            # has at least one benefit, or participates in a preconditions chain
            and (bool(self.benefits) or self.id in self.campaign.preconditions_chain())
        )

    def _base_can_earn(self) -> bool:
        # cross-participates in can_earn and can_earn_within handling, where a timeframe is added
        return (
            self._base_earn_conditions()
            # is within the timeframe
            and self.starts_at <= datetime.now(timezone.utc) < self.ends_at
        )

    def _can_earn_within(self, stamp: datetime) -> bool:
        # NOTE: This does not check the campaign's eligibility or active status
        return (
            self._base_earn_conditions()
            and self.ends_at > datetime.now(timezone.utc)
            and self.starts_at < stamp
        )

    def can_earn(
        self, channel: Channel | None = None, ignore_channel_status: bool = False
    ) -> bool:
        return (
            self._base_can_earn() and self.campaign._base_can_earn(channel, ignore_channel_status)
        )

    @property
    def can_claim(self) -> bool:
        # https://help.twitch.tv/s/article/mission-based-drops?language=en_US#claiming
        # "If you are unable to claim the Drop in time, you will be able to claim it
        # from the Drops Inventory page until 24 hours after the Drops campaign has ended."
        return (
            self.claim_id is not None
            and not self.is_claimed
            and datetime.now(timezone.utc) < self.campaign.ends_at + timedelta(hours=24)
        )

    def update_claim(self, claim_id: str):
        self.claim_id = claim_id

    async def generate_claim(self) -> None:
        # claim IDs now appear to be constructed from other IDs we have access to
        # Format: UserID#CampaignID#DropID
        # NOTE: This marks a drop as a ready-to-claim, so we may want to later ensure
        # its mining progress is finished first
        auth_state = await self.campaign._twitch.get_auth()
        self.claim_id = f"{auth_state.user_id}#{self.campaign.id}#{self.id}"

    def rewards_text(self, delim: str = ", ") -> str:
        return delim.join(benefit.name for benefit in self.benefits)

    async def claim(self) -> bool:
        result = await self._claim()
        if result:
            self.is_claimed = result
            claim_text = (
                f"{self.campaign.game.name}\n"
                f"{self.rewards_text()} "
                f"({self.campaign.claimed_drops}/{self.campaign.total_drops})"
            )
            # two different claim texts, becase a new line after the game name
            # looks ugly in the output window - replace it with a space
            self._twitch.print(
                _("status", "claimed_drop").format(drop=claim_text.replace('\n', ' '))
            )
            self._twitch.gui.tray.notify(claim_text, _("gui", "tray", "notification_title"))
        else:
            logger.error(f"Drop claim has potentially failed! Drop ID: {self.id}")
        return result

    async def _claim(self) -> bool:
        """
        Returns True if the claim succeeded, False otherwise.
        """
        if self.is_claimed:
            return True
        if not self.can_claim:
            return False
        try:
            response = await self._twitch.gql_request(
                GQL_OPERATIONS["ClaimDrop"].with_variables(
                    {"input": {"dropInstanceID": self.claim_id}}
                )
            )
        except GQLException:
            # regardless of the error, we have to assume
            # the claiming operation has potentially failed
            return False
        data = response["data"]
        if "errors" in data and data["errors"]:
            return False
        elif "claimDropRewards" in data:
            if not data["claimDropRewards"]:
                return False
            elif (
                data["claimDropRewards"]["status"]
                in ("ELIGIBLE_FOR_ALL", "DROP_INSTANCE_ALREADY_CLAIMED")
            ):
                return True
        return False


class TimedDrop(BaseDrop):
    def __init__(
        self, campaign: DropsCampaign, data: JsonType, claimed_benefits: dict[str, datetime]
    ):
        super().__init__(campaign, data, claimed_benefits)
        self.real_current_minutes: int = (
            "self" in data and data["self"]["currentMinutesWatched"] or 0
        )
        self.required_minutes: int = data["requiredMinutesWatched"]
        self.extra_current_minutes: int = 0
        if self.is_claimed:
            # claimed drops may report inconsistent current minutes, so we need to overwrite them
            self.real_current_minutes = self.required_minutes

    def __repr__(self) -> str:
        if self.is_claimed:
            additional = ", claimed=True"
        elif self.can_earn():
            additional = ", can_earn=True"
        else:
            additional = ''
        if 0 < self.current_minutes < self.required_minutes:
            minutes = f", {self.current_minutes}/{self.required_minutes}"
        else:
            minutes = ''
        return f"Drop({self.rewards_text()}{minutes}{additional})"

    @property
    def current_minutes(self) -> int:
        return self.real_current_minutes + self.extra_current_minutes

    @property
    def remaining_minutes(self) -> int:
        return self.required_minutes - self.current_minutes

    @property
    def total_required_minutes(self) -> int:
        return self.required_minutes + max(
            (
                self.campaign.timed_drops[pid].total_required_minutes
                for pid in self.precondition_drops
            ),
            default=0,
        )

    @property
    def total_remaining_minutes(self) -> int:
        return self.remaining_minutes + max(
            (
                self.campaign.timed_drops[pid].total_remaining_minutes
                for pid in self.precondition_drops
            ),
            default=0,
        )

    @property
    def progress(self) -> float:
        if self.current_minutes <= 0 or self.required_minutes <= 0:
            return 0.0
        elif self.current_minutes >= self.required_minutes:
            return 1.0
        return self.current_minutes / self.required_minutes

    @property
    def availability(self) -> float:
        now = datetime.now(timezone.utc)
        if self.required_minutes > 0 and self.total_remaining_minutes > 0 and now < self.ends_at:
            return ((self.ends_at - now).total_seconds() / 60) / self.total_remaining_minutes
        return math.inf

    def _base_earn_conditions(self) -> bool:
        return (
            super()._base_earn_conditions()
            and self.required_minutes > 0
            # NOTE: This may be a bad idea, as it invalidates the can_earn status
            # and provides no way to recover from this state until the next reload.
            and self.extra_current_minutes < MAX_EXTRA_MINUTES
        )

    def _on_state_changed(self) -> None:
        self._twitch.gui.inv.update_drop(self)

    def _update_real_minutes(self, delta: int) -> None:
        if delta == 0 or self.real_current_minutes + delta < 0 or not self.can_earn():
            return
        if self.real_current_minutes + delta < self.required_minutes:
            self.real_current_minutes += delta
        else:
            self.real_current_minutes = self.required_minutes
        self.extra_current_minutes = 0
        self._on_state_changed()

    def _bump_minutes(self, channel: Channel | None) -> bool:
        if self.can_earn(channel):
            self.extra_current_minutes += 1
            self._on_state_changed()
            if self.extra_current_minutes >= MAX_EXTRA_MINUTES:
                return True
        return False

    async def claim(self) -> bool:
        result = await super().claim()
        if result:
            self.real_current_minutes = self.required_minutes
            self.extra_current_minutes = 0
        self._on_state_changed()
        return result

    def display(self, *, countdown: bool = True, subone: bool = False):
        self._twitch.gui.display_drop(self, countdown=countdown, subone=subone)

    def update_minutes(self, new_minutes: int):
        delta: int = new_minutes - self.real_current_minutes
        if delta == 0:
            return
        elif self.real_current_minutes + delta < 0:
            delta = -self.real_current_minutes
        elif self.real_current_minutes + delta > self.required_minutes:
            delta = self.required_minutes - self.real_current_minutes
        self.campaign._update_real_minutes(delta)

    def update_progress(
        self,
        drop_self_data: JsonType | None,
        claimed_benefits: dict[str, datetime],
    ) -> bool:
        """
        Quick update: updates drop progress from Inventory GQL 'self' data.
        Preserves extra_current_minutes when possible.
        Returns True if anything changed.
        """
        changed = False
        if drop_self_data is not None:
            new_claim_id: str | None = drop_self_data.get("dropInstanceID")
            new_is_claimed: bool = drop_self_data.get("isClaimed", False)
            new_minutes: int = drop_self_data.get("currentMinutesWatched", 0)
        else:
            # No self data available - preserve current state,
            # but check claimed_benefits as a fallback
            new_claim_id = self.claim_id
            new_is_claimed = self.is_claimed
            new_minutes = self.real_current_minutes
            if not self.is_claimed and self._infer_claimed(claimed_benefits):
                new_is_claimed = True

        if new_claim_id != self.claim_id:
            self.claim_id = new_claim_id
            changed = True
        if new_is_claimed != self.is_claimed:
            self.is_claimed = new_is_claimed
            if new_is_claimed:
                self.real_current_minutes = self.required_minutes
                self.extra_current_minutes = 0
            changed = True
        elif new_minutes != self.real_current_minutes:
            # Only update minutes if claim status didn't change to claimed
            if new_minutes > self.real_current_minutes:
                # API confirmed progress ahead of our estimate - reset extra
                self.extra_current_minutes = 0
            self.real_current_minutes = min(new_minutes, self.required_minutes)
            changed = True

        if changed:
            self._on_state_changed()
        return changed

    def update_from_data(
        self, data: JsonType, claimed_benefits: dict[str, datetime]
    ) -> bool:
        """
        Full update from merged API data (CampaignDetails).
        Updates all fields including benefits, preconditions, required minutes.
        Returns True if anything changed.
        """
        changed = False

        # Update claim/progress from self data
        drop_self = data.get("self") if "self" in data and data["self"] else None
        changed = self.update_progress(drop_self, claimed_benefits) or changed

        # Update fields that only come from CampaignDetails
        new_required: int = data["requiredMinutesWatched"]
        if new_required != self.required_minutes:
            self.required_minutes = new_required
            changed = True

        new_name: str = data["name"]
        if new_name != self.name:
            self.name = new_name
            changed = True

        # Update time window
        new_starts_at = timestamp(data["startAt"])
        new_ends_at = timestamp(data["endAt"])
        if new_starts_at != self.starts_at:
            self.starts_at = new_starts_at
            changed = True
        if new_ends_at != self.ends_at:
            self.ends_at = new_ends_at
            changed = True

        # Update preconditions
        new_preconditions = [d["id"] for d in (data["preconditionDrops"] or [])]
        if new_preconditions != self.precondition_drops:
            self.precondition_drops = new_preconditions
            changed = True

        # Benefits rarely change, but handle it
        new_benefit_ids = sorted(b["benefit"]["id"] for b in (data["benefitEdges"] or []))
        old_benefit_ids = sorted(b.id for b in self.benefits)
        if new_benefit_ids != old_benefit_ids:
            self.benefits = [Benefit(b) for b in (data["benefitEdges"] or [])]
            changed = True

        if changed:
            self._on_state_changed()
        return changed


class DropsCampaign:
    def __init__(self, twitch: Twitch, data: JsonType, claimed_benefits: dict[str, datetime]):
        self._twitch: Twitch = twitch
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.game: Game = Game(data["game"])
        self.linked: bool = data["self"]["isAccountConnected"]
        self.link_url: str = data["accountLinkURL"]
        # campaign's image actually comes from the game object
        # we use regex to get rid of the dimensions part (ex. ".../game_id-285x380.jpg")
        self.image_url: URLType = remove_dimensions(data["game"]["boxArtURL"])
        self.starts_at: datetime = timestamp(data["startAt"])
        self.ends_at: datetime = timestamp(data["endAt"])
        self._valid: bool = data["status"] != "EXPIRED"
        allowed: JsonType = data["allow"]
        self.allowed_channels: list[Channel] = (
            [Channel.from_acl(twitch, channel_data) for channel_data in allowed["channels"]]
            if allowed["channels"] and allowed.get("isEnabled", True) else []
        )
        self.timed_drops: dict[str, TimedDrop] = {
            drop_data["id"]: TimedDrop(self, drop_data, claimed_benefits)
            for drop_data in data["timeBasedDrops"]
        }

    def __repr__(self) -> str:
        return f"Campaign({self.game!s}, {self.name}, {self.claimed_drops}/{self.total_drops})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def drops(self) -> abc.Iterable[TimedDrop]:
        return self.timed_drops.values()

    @property
    def time_triggers(self) -> set[datetime]:
        return set(
            chain(
                (self.starts_at, self.ends_at),
                *((d.starts_at, d.ends_at) for d in self.timed_drops.values()),
            )
        )

    @property
    def active(self) -> bool:
        return self._valid and self.starts_at <= datetime.now(timezone.utc) < self.ends_at

    @property
    def upcoming(self) -> bool:
        return self._valid and datetime.now(timezone.utc) < self.starts_at

    @property
    def expired(self) -> bool:
        return not self._valid or self.ends_at <= datetime.now(timezone.utc)

    @property
    def total_drops(self) -> int:
        return len(self.timed_drops)

    @property
    def eligible(self) -> bool:
        if self.has_badge_or_emote:
            return self._twitch.settings.enable_badges_emotes
        return self.linked

    @cached_property
    def has_badge_or_emote(self) -> bool:
        return any(
            benefit.type.is_badge_or_emote() for drop in self.drops for benefit in drop.benefits
        )

    @property
    def finished(self) -> bool:
        return all(d.is_claimed or d.required_minutes <= 0 for d in self.drops)

    @property
    def claimed_drops(self) -> int:
        return sum(d.is_claimed for d in self.drops)

    @property
    def remaining_drops(self) -> int:
        return sum(not d.is_claimed for d in self.drops)

    @property
    def required_minutes(self) -> int:
        return max(d.total_required_minutes for d in self.drops)

    @property
    def remaining_minutes(self) -> int:
        return max(d.total_remaining_minutes for d in self.drops)

    @property
    def progress(self) -> float:
        return sum(d.progress for d in self.drops) / self.total_drops

    @property
    def availability(self) -> float:
        return min(d.availability for d in self.drops)

    @property
    def first_drop(self) -> TimedDrop | None:
        drops: list[TimedDrop] = sorted(
            (drop for drop in self.drops if drop.can_earn()),
            key=lambda d: d.remaining_minutes,
        )
        return drops[0] if drops else None

    def _update_real_minutes(self, delta: int) -> None:
        for drop in self.drops:
            drop._update_real_minutes(delta)
        if (first_drop := self.first_drop) is not None:
            first_drop.display()

    def _base_can_earn(
        self, channel: Channel | None = None, ignore_channel_status: bool = False
    ) -> bool:
        return (
            self.eligible  # account is eligible
            and self.active  # campaign is active (and valid)
            and (
                channel is None or (  # channel isn't specified,
                    # or there's no ACL, or the channel is in the ACL
                    (not self.allowed_channels or channel in self.allowed_channels)
                    # and the channel is live and playing the campaign's game,
                    # or this campaign can be earned anywhere (special game)
                    and (
                        ignore_channel_status
                        or channel.game is not None and channel.game == self.game
                        or self.game.is_special_events()
                    )
                )
            )
        )

    def get_drop(self, drop_id: str) -> TimedDrop | None:
        return self.timed_drops.get(drop_id)

    def preconditions_chain(self) -> set[str]:
        return set(
            chain.from_iterable(
                drop.precondition_drops for drop in self.drops if not drop.is_claimed
            )
        )

    def can_earn(
        self, channel: Channel | None = None, ignore_channel_status: bool = False
    ) -> bool:
        # True if any of the containing drops can be earned
        return (
            self._base_can_earn(channel, ignore_channel_status)
            and any(drop._base_can_earn() for drop in self.drops)
        )

    def can_earn_within(self, stamp: datetime) -> bool:
        # Same as can_earn, but doesn't check the channel
        # and uses a future timestamp to see if we can earn this campaign later
        return (
            self.eligible
            and self._valid
            and self.ends_at > datetime.now(timezone.utc)
            and self.starts_at < stamp
            and any(drop._can_earn_within(stamp) for drop in self.drops)
        )

    def bump_minutes(self, channel: Channel) -> None:
        # NOTE: Use a temporary list to ensure all drops are bumped before checking
        if any([drop._bump_minutes(channel) for drop in self.drops]):
            # Executes if any drop's extra_current_minutes reach MAX_ESTIMATED_MINUTES
            # TODO: Figure out a better way to handle this case
            logger.warning(
                f"At least one of the drops in campaign \"{self.name}({self.game.name})\" "
                "has reached the maximum extra minutes limit!"
            )
            self._twitch.change_state(State.CHANNEL_SWITCH)
        if (first_drop := self.first_drop) is not None:
            first_drop.display()

    def update_progress(
        self,
        inventory_campaign_data: JsonType,
        claimed_benefits: dict[str, datetime],
    ) -> bool:
        """
        Quick update: updates drop progress from Inventory GQL campaign data.
        Used during quick checks (every reload interval). Only touches
        drop self data (currentMinutesWatched, isClaimed, dropInstanceID).
        Returns True if anything changed.
        """
        changed = False
        for drop_data in inventory_campaign_data.get("timeBasedDrops", []):
            drop_id = drop_data["id"]
            existing_drop = self.timed_drops.get(drop_id)
            if existing_drop is not None:
                drop_self = drop_data.get("self")
                if existing_drop.update_progress(drop_self, claimed_benefits):
                    changed = True
        return changed

    def update_metadata(self, campaigns_data: JsonType) -> bool:
        """
        Quick update: updates campaign status and linked status from
        Campaigns GQL basic data. Used during quick checks.
        Returns True if anything changed.
        """
        changed = False

        new_valid = campaigns_data.get("status", "ACTIVE") != "EXPIRED"
        if new_valid != self._valid:
            self._valid = new_valid
            changed = True

        if "self" in campaigns_data and campaigns_data["self"]:
            new_linked = campaigns_data["self"].get("isAccountConnected", self.linked)
            if new_linked != self.linked:
                self.linked = new_linked
                changed = True

        return changed

    def update_from_data(
        self, data: JsonType, claimed_benefits: dict[str, datetime]
    ) -> bool:
        """
        Full update from complete merged API data (Inventory + Campaigns + CampaignDetails).
        Updates all fields including ACL, drops, benefits.
        Used during full syncs (every FULL_SYNC_INTERVAL reloads).
        Returns True if anything changed.
        """
        changed = False

        # Status and linked
        new_valid = data["status"] != "EXPIRED"
        if new_valid != self._valid:
            self._valid = new_valid
            changed = True

        new_linked: bool = data["self"]["isAccountConnected"]
        if new_linked != self.linked:
            self.linked = new_linked
            changed = True

        # ACL channels - compare by channel IDs to avoid unnecessary object churn
        allowed: JsonType = data["allow"]
        new_acl_ids: set[int] = set()
        if allowed["channels"] and allowed.get("isEnabled", True):
            new_acl_ids = {int(ch["id"]) for ch in allowed["channels"]}
        old_acl_ids = {ch.id for ch in self.allowed_channels}
        if new_acl_ids != old_acl_ids:
            self.allowed_channels = (
                [Channel.from_acl(self._twitch, ch) for ch in allowed["channels"]]
                if allowed["channels"] and allowed.get("isEnabled", True) else []
            )
            changed = True

        # Timed drops - diff by ID
        new_drop_ids = {d["id"] for d in data["timeBasedDrops"]}
        old_drop_ids = set(self.timed_drops.keys())

        # Remove deleted drops
        for drop_id in old_drop_ids - new_drop_ids:
            del self.timed_drops[drop_id]
            changed = True

        # Update existing and add new drops
        for drop_data in data["timeBasedDrops"]:
            drop_id = drop_data["id"]
            existing = self.timed_drops.get(drop_id)
            if existing is not None:
                if existing.update_from_data(drop_data, claimed_benefits):
                    changed = True
            else:
                self.timed_drops[drop_id] = TimedDrop(self, drop_data, claimed_benefits)
                changed = True

        # Invalidate cached properties if benefits may have changed
        if changed and "has_badge_or_emote" in self.__dict__:
            del self.__dict__["has_badge_or_emote"]

        return changed
