from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, Float, Enum as SqlEnum
from datetime import date
from enum import Enum

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class ExpenseCategory(Enum):
    BILLS = "Bills"
    CLOTHING = "Clothing"
    FOOD = "Food"
    GROCERIES = "Groceries"
    HEALTH = "Health"
    LEISURE = "Leisure"
    SAVINGS = "Savings"
    TRANSPORT = "Transport"
    OTHERS = "Others"

class User(db.Model):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

    expense = relationship("ExpenseEntry", back_populates="author")

class ExpenseEntry(db.Model):
    __tablename__ = "expense_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    # databases store Enum names, not their values. By using values_callable parameter, override the default behavior and align the Enum values.
    # credit: https://github.com/sqlalchemy/sqlalchemy/discussions/11527
    category: Mapped[ExpenseCategory] = mapped_column(SqlEnum(ExpenseCategory, values_callable=lambda e: [x.value for x in e]), nullable=False)
    expense_date: Mapped[date] = mapped_column(DateTime, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("user.id"))

    author = relationship("User", back_populates="expense")