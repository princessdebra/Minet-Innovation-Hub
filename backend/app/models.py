from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        String, Table, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

challenge_types = Table(
    "challenge_types", Base.metadata,
    Column("challenge_id", ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True),
    Column("type_id", ForeignKey("innovation_types.id"), primary_key=True),
)
idea_types = Table(
    "idea_types", Base.metadata,
    Column("idea_id", ForeignKey("ideas.id", ondelete="CASCADE"), primary_key=True),
    Column("type_id", ForeignKey("innovation_types.id"), primary_key=True),
)
experiment_types = Table(
    "experiment_types", Base.metadata,
    Column("experiment_id", ForeignKey("experiments.id", ondelete="CASCADE"), primary_key=True),
    Column("type_id", ForeignKey("innovation_types.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    initials: Mapped[str] = mapped_column(String(4))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    # Used by RBAC later. In the POC every role is allowed everything.
    role: Mapped[str] = mapped_column(String(40), default="Employee")


class Horizon(Base):
    __tablename__ = "horizons"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    description: Mapped[str] = mapped_column(String(200))
    short_description: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class InnovationType(Base):
    __tablename__ = "innovation_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    short_description: Mapped[str] = mapped_column(String(160))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Stage(Base):
    __tablename__ = "stages"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    description: Mapped[str] = mapped_column(String(240))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    how_might_we: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40))
    horizon_id: Mapped[int] = mapped_column(ForeignKey("horizons.id"))
    sponsor: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    is_illustrative: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    background: Mapped[Optional[str]] = mapped_column(Text)
    success_looks_like: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    horizon: Mapped[Horizon] = relationship()
    types: Mapped[list[InnovationType]] = relationship(
        secondary=challenge_types, order_by="InnovationType.sort_order")


class Idea(Base):
    __tablename__ = "ideas"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(24), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    problem: Mapped[Optional[str]] = mapped_column(Text)
    solution: Mapped[Optional[str]] = mapped_column(Text)
    expected_value: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    collaborators: Mapped[Optional[str]] = mapped_column(String(300))
    horizon_id: Mapped[Optional[int]] = mapped_column(ForeignKey("horizons.id"))
    horizon_unsure: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="Draft")
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sponsor: Mapped[Optional[str]] = mapped_column(String(120))
    next_label: Mapped[str] = mapped_column(String(40), default="Next action")
    next_text: Mapped[Optional[str]] = mapped_column(String(240))
    action_label: Mapped[Optional[str]] = mapped_column(String(160))
    review_notes: Mapped[Optional[dict]] = mapped_column(JSON)
    challenge_id: Mapped[Optional[int]] = mapped_column(ForeignKey("challenges.id"))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    is_illustrative: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    owner: Mapped[User] = relationship()
    horizon: Mapped[Optional[Horizon]] = relationship()
    stage: Mapped[Stage] = relationship()
    challenge: Mapped[Optional[Challenge]] = relationship()
    types: Mapped[list[InnovationType]] = relationship(
        secondary=idea_types, order_by="InnovationType.sort_order")


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    horizon_id: Mapped[int] = mapped_column(ForeignKey("horizons.id"))
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"))
    status: Mapped[str] = mapped_column(String(30))
    sponsor: Mapped[Optional[str]] = mapped_column(String(120))
    next_label: Mapped[str] = mapped_column(String(40), default="Next action")
    next_text: Mapped[Optional[str]] = mapped_column(String(240))
    next_decision_date: Mapped[Optional[date]] = mapped_column(Date)
    action_label: Mapped[Optional[str]] = mapped_column(String(160))
    evidence_learning: Mapped[Optional[str]] = mapped_column(Text)
    resource_decision: Mapped[Optional[str]] = mapped_column(Text)
    review_notes: Mapped[Optional[dict]] = mapped_column(JSON)
    idea_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ideas.id"))
    is_illustrative: Mapped[bool] = mapped_column(Boolean, default=False)

    owner: Mapped[User] = relationship()
    horizon: Mapped[Horizon] = relationship()
    stage: Mapped[Stage] = relationship()
    types: Mapped[list[InnovationType]] = relationship(
        secondary=experiment_types, order_by="InnovationType.sort_order")


class LearningPath(Base):
    __tablename__ = "learning_paths"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(300))
    section: Mapped[str] = mapped_column(String(20), default="catalog")  # recommended | next | catalog
    badge: Mapped[Optional[str]] = mapped_column(String(20))
    footer_label: Mapped[Optional[str]] = mapped_column(String(80))
    cta_label: Mapped[Optional[str]] = mapped_column(String(40))
    recommended_for: Mapped[Optional[str]] = mapped_column(String(200))
    action_label: Mapped[Optional[str]] = mapped_column(String(160))
    linked_experiment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("experiments.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    modules: Mapped[list["LearningModule"]] = relationship(
        order_by="LearningModule.sort_order", cascade="all, delete-orphan")


class LearningModule(Base):
    __tablename__ = "learning_modules"
    id: Mapped[int] = mapped_column(primary_key=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[Optional[str]] = mapped_column(String(300))
    minutes: Mapped[int] = mapped_column(Integer, default=10)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class UserPathProgress(Base):
    __tablename__ = "user_path_progress"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_paths.id"), primary_key=True)
    completed_modules: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class MentorRequest(Base):
    __tablename__ = "mentor_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    area: Mapped[str] = mapped_column(String(60))
    message: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="Requested")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CommunityMember(Base):
    __tablename__ = "community_members"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImpactMetric(Base):
    __tablename__ = "impact_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    horizon_id: Mapped[int] = mapped_column(ForeignKey("horizons.id"))
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="To be measured")
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    benefits_owner: Mapped[Optional[str]] = mapped_column(String(120))
    measurement_period: Mapped[Optional[str]] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def validated(self) -> bool:
        """A benefit is validated only with evidence, a named owner and a measurement period."""
        return all(bool((v or "").strip()) for v in
                   (self.evidence, self.benefits_owner, self.measurement_period))


class PortfolioStat(Base):
    __tablename__ = "portfolio_stats"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    value: Mapped[Optional[int]] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class LibraryItem(Base):
    __tablename__ = "library_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(400))
    kind: Mapped[str] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
