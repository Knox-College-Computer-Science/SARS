from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    school_email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    initials = Column(String(4), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    messages = relationship("ChannelMessage", back_populates="sender")
    direct_messages = relationship("DirectMessage", back_populates="sender")
    enrollments = relationship("CourseEnrollment", back_populates="user")
    conversations = relationship("ConversationParticipant", back_populates="user")


class Course(Base):
    __tablename__ = "courses"

    id = Column(String, primary_key=True, default=generate_uuid)
    school_course_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    course_code = Column(String, nullable=False)
    teacher_name = Column(String)
    term = Column(String, default="Spring 2026")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    enrollments = relationship("CourseEnrollment", back_populates="course")
    channels = relationship("Channel", back_populates="course")


class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    course_id = Column(String, ForeignKey("courses.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    role = Column(String, default="student")  # student / teacher
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course", back_populates="enrollments")
    user = relationship("User", back_populates="enrollments")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, default=generate_uuid)
    course_id = Column(String, ForeignKey("courses.id"), nullable=False)
    name = Column(String, nullable=False)
    channel_type = Column(String, default="general")  # general / announcements / custom
    position = Column(Integer, default=0)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    course = relationship("Course", back_populates="channels")
    messages = relationship("ChannelMessage", back_populates="channel")


class ChannelMessage(Base):
    __tablename__ = "channel_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    channel_id = Column(String, ForeignKey("channels.id"), nullable=False)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    reply_to_id = Column(String, ForeignKey("channel_messages.id"), nullable=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    reactions = relationship("MessageReaction", back_populates="message", cascade="all, delete-orphan")


class MessageReaction(Base):
    __tablename__ = "message_reactions"

    id = Column(String, primary_key=True, default=generate_uuid)
    message_id = Column(String, ForeignKey("channel_messages.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    emoji = Column(String(8), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_msg_reaction"),
    )

    message = relationship("ChannelMessage", back_populates="reactions")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())

    participants = relationship("ConversationParticipant", back_populates="conversation")
    messages = relationship("DirectMessage", back_populates="conversation")


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    conversation_id = Column(String, ForeignKey("conversations.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    last_read_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User", back_populates="conversations")


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", back_populates="direct_messages")
