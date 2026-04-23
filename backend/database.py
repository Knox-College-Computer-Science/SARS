import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / "nexus.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

engine_options = {}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models

    Base.metadata.create_all(bind=engine)
    apply_dev_migrations()

    with SessionLocal() as db:
        seed_demo_data(db, models)


def seed_demo_data(db: Session, models):
    user_specs = {
        "me": {
            "school_email": "demo.student@school.edu",
            "display_name": "Test Student",
            "initials": "TS",
        },
        "sarah": {
            "school_email": "sarah.johnson@school.edu",
            "display_name": "Sarah Johnson",
            "initials": "SJ",
        },
        "marcus": {
            "school_email": "marcus.lee@school.edu",
            "display_name": "Marcus Lee",
            "initials": "ML",
        },
        "priya": {
            "school_email": "priya.kumar@school.edu",
            "display_name": "Priya Kumar",
            "initials": "PK",
        },
        "teacher": {
            "school_email": "dr.martinez@school.edu",
            "display_name": "Dr. Martinez",
            "initials": "DM",
        },
    }

    users = {}
    for key, spec in user_specs.items():
        user = db.query(models.User).filter(models.User.school_email == spec["school_email"]).first()
        if not user:
            user = models.User(**spec)
            db.add(user)
            db.flush()
        users[key] = user

    course = (
        db.query(models.Course)
        .filter(models.Course.school_course_id == "CHEM101")
        .first()
    )
    if not course:
        course = models.Course(
            school_course_id="CHEM101",
            name="Introduction to Chemistry",
            course_code="CHEM101",
            teacher_name="Dr. Martinez",
            term="Spring 2026",
        )
        db.add(course)
        db.flush()

    for key, user in users.items():
        enrollment = (
            db.query(models.CourseEnrollment)
            .filter(
                models.CourseEnrollment.course_id == course.id,
                models.CourseEnrollment.user_id == user.id,
            )
            .first()
        )
        if not enrollment:
            enrollment = models.CourseEnrollment(
                course_id=course.id,
                user_id=user.id,
                role="teacher" if key == "teacher" else "student",
            )
            db.add(enrollment)

    channel_specs = [
        {"name": "general", "channel_type": "general", "position": 0},
        {"name": "announcements", "channel_type": "announcements", "position": 1},
        {"name": "homework-help", "channel_type": "custom", "position": 2},
        {"name": "lab-partners", "channel_type": "custom", "position": 3},
    ]

    channels = {}
    for spec in channel_specs:
        channel = (
            db.query(models.Channel)
            .filter(
                models.Channel.course_id == course.id,
                models.Channel.name == spec["name"],
            )
            .first()
        )
        if not channel:
            channel = models.Channel(course_id=course.id, **spec)
            db.add(channel)
            db.flush()
        channels[spec["name"]] = channel

    now = datetime.now(timezone.utc)

    if db.query(models.ChannelMessage).count() == 0:
        channel_messages = {
            "general": [
                (
                    "sarah",
                    "Hey everyone! Does anyone understand question 3 on the homework? I keep getting a different answer than what's in the back of the book.",
                ),
                (
                    "marcus",
                    "Yeah I think you need to use the ideal gas law for that one. PV = nRT. What values did you get for P and T?",
                ),
                (
                    "sarah",
                    "P = 2.5 atm, T = 300K. I got n = 0.1 mol but the answer key says 0.102.",
                ),
            ],
            "announcements": [
                (
                    "teacher",
                    "Reminder: Lab report due this Friday by 11:59 PM. Submit via the course portal.",
                ),
                (
                    "teacher",
                    "Office hours move to Thursday from 3 PM to 5 PM this week because of a faculty meeting.",
                ),
            ],
            "homework-help": [
                (
                    "priya",
                    "Can someone explain what limiting reagent means in simple terms?",
                ),
                (
                    "marcus",
                    "Think of it like the ingredient in a recipe that runs out first. Once it is gone, the reaction stops.",
                ),
            ],
            "lab-partners": [
                (
                    "sarah",
                    "Looking for a lab partner for next Tuesday. Anyone free after 10 AM?",
                ),
            ],
        }

        for channel_name, entries in channel_messages.items():
            for index, (sender_key, content) in enumerate(entries):
                db.add(
                    models.ChannelMessage(
                        channel_id=channels[channel_name].id,
                        sender_id=users[sender_key].id,
                        content=content,
                        sent_at=now - timedelta(minutes=24 - (index * 3)),
                    )
                )

    if db.query(models.Conversation).count() == 0:
        conversation_specs = {
            "sarah": [
                ("sarah", "Hey! Are you coming to the study session tomorrow?"),
                ("me", "Yeah, what time does it start?"),
                ("sarah", "3 PM in the library, room 204."),
            ],
            "marcus": [
                ("marcus", "Did you get the notes from Thursday? I was sick."),
            ],
            "priya": [
                ("priya", "Want to form a study group for the midterm next week?"),
            ],
        }

        for index, (peer_key, entries) in enumerate(conversation_specs.items()):
            conversation = models.Conversation(
                last_message_at=now - timedelta(hours=index + 1),
            )
            db.add(conversation)
            db.flush()

            db.add(
                models.ConversationParticipant(
                    conversation_id=conversation.id,
                    user_id=users["me"].id,
                    last_read_at=now,
                )
            )
            db.add(
                models.ConversationParticipant(
                    conversation_id=conversation.id,
                    user_id=users[peer_key].id,
                    last_read_at=now,
                )
            )

            for message_index, (sender_key, content) in enumerate(entries):
                sent_at = now - timedelta(hours=index + 1) + timedelta(minutes=message_index * 4)
                db.add(
                    models.DirectMessage(
                        conversation_id=conversation.id,
                        sender_id=users[sender_key].id,
                        content=content,
                        sent_at=sent_at,
                    )
                )
                conversation.last_message_at = sent_at

    db.commit()


def apply_dev_migrations():
    inspector = inspect(engine)
    if "courses" not in inspector.get_table_names():
        return

    course_columns = {column["name"] for column in inspector.get_columns("courses")}
    with engine.begin() as connection:
        if "term" not in course_columns:
            connection.execute(text("ALTER TABLE courses ADD COLUMN term VARCHAR"))
            connection.execute(
                text("UPDATE courses SET term = 'Spring 2026' WHERE term IS NULL")
            )
