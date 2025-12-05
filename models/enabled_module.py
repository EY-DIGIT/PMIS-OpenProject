"""
EnabledModule model - Tracks which modules are enabled per project.

Based on OpenProject stable/16 branch EnabledModule model.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Index

from sqlalchemy.orm import relationship

try:
    from ..database import Base
except ImportError:
    try:
        from database import Base
    except ImportError:
        from db_models import Base


class EnabledModule(Base):
    """
    EnabledModule model - Feature flags for projects.

    Available modules include:
    - work_package_tracking
    - wiki
    - calendar
    - board
    - news
    - forums
    - documents
    - time_tracking
    - gantt
    - budget
    - costs
    - repository

    Attributes:
        id: Primary key
        project_id: Reference to Project
        name: Module name
    """
    __tablename__ = 'enabled_modules'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="enabled_modules")

    # Table args with indexes
    __table_args__ = (
        Index('idx_enabled_modules_project_id', 'project_id'),
        Index('idx_enabled_modules_name', 'name'),
    )

    def __repr__(self):
        return f"<EnabledModule(id={self.id}, project_id={self.project_id}, name='{self.name}')>"


# Available module names
AVAILABLE_MODULES = [
    'work_package_tracking',
    'wiki',
    'calendar',
    'board',
    'news',
    'forums',
    'documents',
    'time_tracking',
    'gantt',
    'budget',
    'costs',
    'repository',
]

# Default modules enabled for new projects
DEFAULT_MODULES = [
    'work_package_tracking',
    'wiki',
    'calendar',
    'board',
]
