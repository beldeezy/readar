from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON, ARRAY, Float, UniqueConstraint, event
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PostgresEnum
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from enum import Enum
import sqlalchemy as sa
from app.database import Base
import logging

logger = logging.getLogger(__name__)


class SubscriptionStatus(str, Enum):
    FREE = "free"
    ACTIVE = "active"
    CANCELED = "canceled"


class BusinessStage(str, Enum):
    IDEA = "idea"
    PRE_REVENUE = "pre-revenue"
    EARLY_REVENUE = "early-revenue"
    SCALING = "scaling"


class BookDifficulty(str, Enum):
    """
    Book difficulty enum with lowercase values for Postgres compatibility.
    
    Values are lowercase ("light", "medium", "deep") so SQLAlchemy writes
    values that Postgres accepts.
    """
    LIGHT = "light"
    MEDIUM = "medium"
    DEEP = "deep"


class UserBookStatus(str, enum.Enum):
    READ_LIKED = "read_liked"
    READ_DISLIKED = "read_disliked"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_user_id = Column(String, unique=True, index=True, nullable=True)  # Supabase user UUID
    email = Column(String, unique=True, index=True, nullable=True)  # Made nullable for Supabase users
    password_hash = Column(String, nullable=True)  # Made nullable for Supabase users (no password needed)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subscription_status = Column(
        PostgresEnum(
            SubscriptionStatus,
            values_callable=lambda x: [e.value for e in x],
            name="subscriptionstatus",
            create_type=False,  # Type already exists in DB
        ),
        nullable=False,
        server_default="free",  # DB-level default as string value
        default=SubscriptionStatus.FREE,  # Python-level default as enum object
    )
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    # Relationships
    onboarding_profile = relationship("OnboardingProfile", back_populates="user", uselist=False)
    book_interactions = relationship("UserBookInteraction", back_populates="user")
    recommendation_sessions = relationship("RecommendationSession", back_populates="user")


class OnboardingProfile(Base):
    __tablename__ = "onboarding_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    occupation = Column(String, nullable=True)
    entrepreneur_status = Column(String, nullable=True)
    location = Column(String, nullable=True)
    economic_sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    business_model = Column(String, nullable=False)
    business_experience = Column(String, nullable=True)
    areas_of_business = Column(ARRAY(String), nullable=True)
    business_stage = Column(
        PostgresEnum(
            BusinessStage,
            values_callable=lambda x: [e.value for e in x],
            name="businessstage",
            create_type=False,  # Type already exists in DB
        ),
        nullable=False,
    )
    org_size = Column(String, nullable=True)
    is_student = Column(Boolean, nullable=True)
    biggest_challenge = Column(Text, nullable=False)
    vision_6_12_months = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    current_gross_revenue = Column(String, nullable=True)
    has_prior_reading_history = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="onboarding_profile")


class Book(Base):
    __tablename__ = "books"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    author_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    thumbnail_url = Column(String, nullable=True)
    cover_image_url = Column(String, nullable=True)
    purchase_url = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)
    published_year = Column(Integer, nullable=True)
    # Google Books enrichment fields
    language = Column(String, nullable=True)
    isbn_10 = Column(String, nullable=True)
    isbn_13 = Column(String, nullable=True)
    average_rating = Column(Float, nullable=True)
    ratings_count = Column(Integer, nullable=True)
    categories = Column(ARRAY(String), nullable=True)
    business_stage_tags = Column(ARRAY(String), nullable=True)
    functional_tags = Column(ARRAY(String), nullable=True)
    theme_tags = Column(ARRAY(String), nullable=True)
    difficulty = Column(SQLEnum(BookDifficulty), nullable=True)
    # Insight fields
    promise = Column(Text, nullable=True)
    best_for = Column(Text, nullable=True)
    core_frameworks = Column(JSONB, nullable=True)
    anti_patterns = Column(JSONB, nullable=True)
    outcomes = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user_interactions = relationship("UserBookInteraction", back_populates="book")


class UserBookInteraction(Base):
    __tablename__ = "user_book_interactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id"), nullable=False)
    status = Column(SQLEnum(UserBookStatus), nullable=False)
    rating = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="book_interactions")
    book = relationship("Book", back_populates="user_interactions")


class RecommendationSession(Base):
    __tablename__ = "recommendation_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    request_payload = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="recommendation_sessions")


class ReadingHistoryEntry(Base):
    __tablename__ = "reading_history_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    my_rating = Column(Float, nullable=True)
    date_read = Column(String, nullable=True)  # keep raw string from Goodreads for now
    shelf = Column(String, nullable=True)
    source = Column(String, nullable=False, default="goodreads")
    created_at = Column(
        DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


class EventLog(Base):
    __tablename__ = "event_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    event_name = Column(String, nullable=False, index=True)
    properties = Column(JSONB, nullable=True)
    request_id = Column(String, nullable=True)
    session_id = Column(String, nullable=True)


class UserBookStatusModel(Base):
    """
    Latest book status for each user-book pair.
    This table stores the current status (interested, read_liked, read_disliked, not_for_me)
    and powers the Profile dashboard lists.
    """
    __tablename__ = "user_book_status"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    book_id = Column(String, nullable=False, index=True)  # Using String to match book IDs (may be UUID or string)
    status = Column(String, nullable=False)  # one of: interested | read_liked | read_disliked | not_for_me
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'book_id', name='uq_user_book_status_user_book'),
    )


class FeedbackSentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class FeedbackState(str, enum.Enum):
    INTERESTED = "interested"
    READ_COMPLETED = "read_completed"
    DISMISSED = "dismissed"


class UserBookFeedback(Base):
    """
    Append-only feedback table to capture user intent without affecting recommendations yet.
    This is a normalized, immutable record of user feedback actions.
    """
    __tablename__ = "user_book_feedback"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    book_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    sentiment = Column(SQLEnum(FeedbackSentiment), nullable=False)
    state = Column(SQLEnum(FeedbackState), nullable=False)
    source = Column(String, nullable=False, default="recommendations_v1")
    created_at = Column(DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    
    __table_args__ = (
        sa.Index('idx_user_book_feedback_user_book', 'user_id', 'book_id'),
    )


# ----------------------------
# SQLAlchemy Event Listeners for subscription_status normalization
# ----------------------------
def _normalize_subscription_status_for_db(value) -> SubscriptionStatus:
    """
    Normalize subscription_status before database insert/update.
    This is a safety net to catch any code path that passes "FREE" or other invalid values.
    """
    if value is None:
        return SubscriptionStatus.FREE
    
    if isinstance(value, SubscriptionStatus):
        # Verify the enum value is correct (should be "free", "active", or "canceled")
        if value.value not in ["free", "active", "canceled"]:
            logger.warning(f"Invalid enum value: {value.value}, normalizing to FREE")
            return SubscriptionStatus.FREE
        return value
    
    if isinstance(value, str):
        value_upper = value.upper()
        value_lower = value.lower()
        
        # Try to match by enum name (e.g., "FREE" -> SubscriptionStatus.FREE)
        for status in SubscriptionStatus:
            if status.name == value_upper:
                return status
        
        # Try to match by enum value (e.g., "free" -> SubscriptionStatus.FREE)
        for status in SubscriptionStatus:
            if status.value == value_lower:
                return status
    
    # Default to FREE if we can't normalize
    logger.warning(f"Could not normalize subscription_status={value} (type={type(value)}), defaulting to FREE")
    return SubscriptionStatus.FREE


@event.listens_for(User, "before_insert", propagate=True)
@event.listens_for(User, "before_update", propagate=True)
def normalize_subscription_status_before_db(mapper, connection, target):
    """
    Event listener that normalizes subscription_status before insert/update.
    This ensures "FREE" string is converted to SubscriptionStatus.FREE ("free") before hitting the DB.
    """
    if hasattr(target, 'subscription_status') and target.subscription_status is not None:
        original = target.subscription_status
        normalized = _normalize_subscription_status_for_db(original)
        
        if original != normalized:
            logger.warning(
                f"[DB NORMALIZATION] Normalizing subscription_status from {original} "
                f"(type={type(original)}, value={getattr(original, 'value', original)}) "
                f"to {normalized} (value={normalized.value})"
            )
            target.subscription_status = normalized
        
        # Final safety check: ensure the value is lowercase "free", "active", or "canceled"
        final_value = target.subscription_status.value if isinstance(target.subscription_status, SubscriptionStatus) else str(target.subscription_status)
        if final_value not in ["free", "active", "canceled"]:
            logger.error(
                f"[CRITICAL DB CHECK] subscription_status has invalid value: {final_value}. "
                f"Force-setting to FREE."
            )
            target.subscription_status = SubscriptionStatus.FREE

