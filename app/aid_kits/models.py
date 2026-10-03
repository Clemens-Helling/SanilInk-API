from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class FirstAidKit(Base):
    __tablename__ = "first_aid_kits"

    kit_id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer, ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    building_id = Column(Integer, nullable=False, index=True)
    label = Column(String(100), nullable=False)
    location_detail = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    building = relationship("Building", back_populates="kits")
    intake_keys = relationship("IntakeKey", back_populates="kit")

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "building_id"],
            ["buildings.customer_id", "buildings.building_id"],
            name="fk_kits_customer_building",
        ),
        # Ziel für den Composite-FK aus intake_keys
        UniqueConstraint("customer_id", "kit_id", name="uq_kits_customer_kit"),
        UniqueConstraint("customer_id", "label", name="uq_kits_customer_label"),
    )


class Article(Base):
    __tablename__ = "articles"

    article_id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer, ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    name = Column(String(150), nullable=False)
    unit = Column(String(50), nullable=False, default="Stück")
    description = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "customer_id", "article_id", name="uq_articles_customer_article"
        ),
        UniqueConstraint("customer_id", "name", name="uq_articles_customer_name"),
    )


class KitItem(Base):
    __tablename__ = "kit_items"

    kit_item_id = Column(Integer, primary_key=True)
    customer_id = Column(
        Integer, ForeignKey("customers.customer_id"), nullable=False, index=True
    )
    kit_id = Column(Integer, ForeignKey("first_aid_kits.kit_id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.article_id"), nullable=False)
    target_quantity = Column(Integer, nullable=False)
    current_quantity = Column(Integer, nullable=False)
    min_quantity = Column(Integer, nullable=False, default=0, server_default="0")
    expiry_date = Column(Date, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    kit = relationship("FirstAidKit", foreign_keys=[kit_id])
    article = relationship("Article", foreign_keys=[article_id])

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "kit_id"],
            ["first_aid_kits.customer_id", "first_aid_kits.kit_id"],
        ),
        ForeignKeyConstraint(
            ["customer_id", "article_id"],
            ["articles.customer_id", "articles.article_id"],
        ),
        UniqueConstraint("kit_id", "article_id", name="uq_kit_items_kit_article"),
        UniqueConstraint(
            "customer_id", "kit_item_id", name="uq_kit_items_customer_item"
        ),
        CheckConstraint("current_quantity >= 0", name="ck_kit_items_current_nonneg"),
        CheckConstraint("target_quantity >= 0", name="ck_kit_items_target_nonneg"),
        CheckConstraint("min_quantity >= 0", name="ck_kit_items_min_nonneg"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    movement_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, nullable=False, index=True)
    kit_item_id = Column(Integer, nullable=False, index=True)
    pending_intake_id = Column(Integer, nullable=True, index=True)
    delta = Column(Integer, nullable=False)
    reason = Column(String(32), nullable=False)
    source = Column(String(16), nullable=False)  # 'staff' | 'intake'
    created_by = Column(Integer, ForeignKey("users.User_ID"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "kit_item_id"],
            ["kit_items.customer_id", "kit_items.kit_item_id"],
        ),
        ForeignKeyConstraint(
            ["customer_id", "pending_intake_id"],
            ["pending_intakes.customer_id", "pending_intakes.pending_intake_id"],
        ),
        CheckConstraint(
            "reason IN ('consumption', 'refill', 'inventory_correction')",
            name="ck_stock_movements_reason",
        ),
        CheckConstraint("delta <> 0", name="ck_stock_movements_delta_nonzero"),
        CheckConstraint(
            "source IN ('staff', 'intake')", name="ck_stock_movements_source_values"
        ),
        # staff: immer ein Benutzer. intake: anonym, nur Entnahme, an eine Meldung gebunden
        CheckConstraint(
            "(source = 'staff' AND created_by IS NOT NULL) "
            "OR (source = 'intake' AND created_by IS NULL "
            "AND pending_intake_id IS NOT NULL "
            "AND reason = 'consumption' AND delta < 0)",
            name="ck_stock_movements_source",
        ),
        # pro Meldung und Artikel nur eine anonyme Buchung
        Index(
            "uq_stock_movements_intake_item",
            "pending_intake_id",
            "kit_item_id",
            unique=True,
            postgresql_where=text("source = 'intake'"),
        ),
    )
