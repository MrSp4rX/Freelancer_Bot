import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum, Float, ForeignKey, Table
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Association Tables for Many-to-Many Relationships ---
user_skills_table = Table('user_skills', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('skill_id', Integer, ForeignKey('skills.id'))
)

job_skills_table = Table('job_skills', Base.metadata,
    Column('job_id', Integer, ForeignKey('jobs.id')),
    Column('skill_id', Integer, ForeignKey('skills.id'))
)

# --- Main Models ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    first_name = Column(String)
    username = Column(String, nullable=True)
    role = Column(Enum('client', 'freelancer', name='user_role_enum'), nullable=True)
    status = Column(Enum('active', 'banned', name='user_status_enum'), default='active', nullable=False)
    admin_notes = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    balance = Column(Float, default=0.0, nullable=False)
    skills = relationship("Skill", secondary=user_skills_table, back_populates="freelancers")
    jobs_posted = relationship("Job", back_populates="client", foreign_keys="[Job.client_id]")
    jobs_hired_for = relationship("Job", back_populates="hired_freelancer", foreign_keys="[Job.hired_freelancer_id]")
    applications = relationship("Application", back_populates="freelancer")
    reviews_given = relationship("Review", back_populates="reviewer", foreign_keys="[Review.reviewer_id]")
    reviews_received = relationship("Review", back_populates="reviewee", foreign_keys="[Review.reviewee_id]")

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=True)
    freelancers = relationship("User", secondary=user_skills_table, back_populates="skills")
    jobs = relationship("Job", secondary=job_skills_table, back_populates="skills_required")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    budget = Column(Float, nullable=False)
    currency = Column(String, nullable=True)
    status = Column(Enum('pending_deposit', 'open', 'in_progress', 'pending_completion', 'completed', 'cancelled', name='job_status_enum'), nullable=False, default='pending_deposit')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    client_id = Column(Integer, ForeignKey('users.id'))
    hired_freelancer_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    client = relationship("User", back_populates="jobs_posted", foreign_keys=[client_id])
    hired_freelancer = relationship("User", back_populates="jobs_hired_for", foreign_keys=[hired_freelancer_id])
    applications = relationship("Application", back_populates="job")
    skills_required = relationship("Skill", secondary=job_skills_table, back_populates="jobs")
    reviews = relationship("Review", back_populates="job")

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    proposal_text = Column(String, nullable=False)
    bid_amount = Column(Float, nullable=False)
    status = Column(Enum('submitted', 'viewed', 'rejected', 'accepted', name='application_status_enum'), nullable=False, default='submitted')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    job_id = Column(Integer, ForeignKey('jobs.id'))
    job = relationship("Job", back_populates="applications")
    freelancer_id = Column(Integer, ForeignKey('users.id'))
    freelancer = relationship("User", back_populates="applications")

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    job_id = Column(Integer, ForeignKey('jobs.id'))
    reviewer_id = Column(Integer, ForeignKey('users.id'))
    reviewee_id = Column(Integer, ForeignKey('users.id'))

    job = relationship("Job", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews_given", foreign_keys=[reviewer_id])
    reviewee = relationship("User", back_populates="reviews_received", foreign_keys=[reviewee_id])

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    type = Column(Enum('deposit', 'withdrawal', 'payment', 'earning', name='transaction_type_enum'), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum('pending', 'completed', 'failed', name='transaction_status_enum'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    related_job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    transaction_hash = Column(String, nullable=True)

    user = relationship("User")

def init_db():
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")

