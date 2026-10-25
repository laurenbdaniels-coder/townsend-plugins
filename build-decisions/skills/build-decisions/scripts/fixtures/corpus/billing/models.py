from sqlalchemy import Column, Integer, String

# SQLAlchemy Core: the attribute and the column name differ (review round 1, S-062)
class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    tax_ref = Column("iban", String)
