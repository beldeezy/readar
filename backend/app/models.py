from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON, ARRAY, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum
import sqlalchemy as sa
from app.database import Base


class SubscriptionStatus(str, enum.Enum):
    FREE = "free"
    ACTIVE = "active"
    CANCELED = "canceled"


class BusinessStage(str, enum.Enum):
    IDEA = "idea"
    PRE_REVENUE = "pre-revenue"
    EARLY_REVENUE = "early-revenue"
    SCALING = "scaling"


class BookDifficulty(str, enum.Enum):
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
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subscription_status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.FREE)
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
    business_stage = Column(SQLEnum(BusinessStage), nullable=False)
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

