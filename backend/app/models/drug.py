from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class GenericDrug(Base):
    __tablename__ = "generic_drugs"

    id = Column(Integer, primary_key=True, index=True)
    generic_name = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=False)

    brands = relationship(
        "BrandDrug",
        back_populates="generic",
        cascade="all, delete-orphan",
    )
    aliases = relationship(
        "DrugAlias",
        back_populates="generic",
        cascade="all, delete-orphan",
    )


class BrandDrug(Base):
    __tablename__ = "brand_drugs"

    id = Column(Integer, primary_key=True, index=True)
    brand_name = Column(String, nullable=False, index=True)
    generic_id = Column(Integer, ForeignKey("generic_drugs.id"), nullable=False, index=True)

    generic = relationship("GenericDrug", back_populates="brands")


class DrugAlias(Base):
    __tablename__ = "drug_aliases"

    id = Column(Integer, primary_key=True, index=True)
    alias_name = Column(String, nullable=False, index=True)
    generic_id = Column(Integer, ForeignKey("generic_drugs.id"), nullable=False, index=True)

    generic = relationship("GenericDrug", back_populates="aliases")
