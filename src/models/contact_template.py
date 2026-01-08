from sqlalchemy import Column, Integer, String, Text

from src.config.database import Base


class ContactTemplate(Base):
    __tablename__ = "contact_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last = Column(String(100), nullable=True)
    first = Column(String(100), nullable=True)
    last_kana = Column(String(100), nullable=True)
    first_kana = Column(String(100), nullable=True)
    last_hira = Column(String(100), nullable=True)
    first_hira = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    url = Column(String(255), nullable=True)
    phone1 = Column(String(20), nullable=True)
    phone2 = Column(String(20), nullable=True)
    phone3 = Column(String(20), nullable=True)
    zip1 = Column(String(10), nullable=True)
    zip2 = Column(String(10), nullable=True)
    address1 = Column(String(255), nullable=True)
    address2 = Column(String(255), nullable=True)
    address3 = Column(String(255), nullable=True)
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
