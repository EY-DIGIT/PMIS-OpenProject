"""
ProjectService - Business logic for project operations.

Based on OpenProject stable/16 branch Projects services.
"""
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

try:
    from models import Project, Member, MemberRole, Role, EnabledModule
    from models.enabled_module import DEFAULT_MODULES
    from schemas.project import ProjectCreate, ProjectUpdate
    from utils import ServiceResult
except ImportError:
    from models import Project, Member, MemberRole, Role, EnabledModule
    from models.enabled_module import DEFAULT_MODULES
    from schemas.project import ProjectCreate, ProjectUpdate
    from utils import ServiceResult


class ProjectService:
    """Service for project operations"""

    def __init__(self, db: Session, user):
        """
        Initialize ProjectService.

        Args:
            db: Database session
            user: Current user object
        """
        self.db = db
        self.user = user

    def create_project(self, data: ProjectCreate) -> ServiceResult:
        """
        Create new project with validation and initialization.

        Args:
            data: ProjectCreate schema

        Returns:
            ServiceResult with created Project or errors
        """
        # 1. Authorization check
        if not self._can_create_project(data.parent_id):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to create project']},
                message="Not authorized to create project"
            )

        # 2. Validate identifier uniqueness
        existing = self.db.query(Project).filter_by(identifier=data.identifier).first()
        if existing:
            return ServiceResult.failure_result(
                errors={'identifier': ['Identifier already exists']},
                message="Identifier already exists"
            )

        # 3. Validate parent if specified
        if data.parent_id:
            parent = self.db.query(Project).get(data.parent_id)
            if not parent:
                return ServiceResult.failure_result(
                    errors={'parent_id': ['Parent project not found']},
                    message="Parent project not found"
                )

        try:
            # 4. Create project
            project = Project(**data.dict())
            self.db.add(project)
            self.db.flush()

            # 5. Initialize project (add creator, enable modules)
            self._initialize_project(project)

            # 6. Update nested set if has parent
            if project.parent_id:
                self._update_nested_set_on_create(project)

            # 7. Commit
            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project created successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'database': [str(e)]},
                message="Database integrity error"
            )
        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error creating project: {str(e)}"
            )

    def update_project(self, project_id: int, data: ProjectUpdate) -> ServiceResult:
        """
        Update existing project.

        Args:
            project_id: Project ID
            data: ProjectUpdate schema

        Returns:
            ServiceResult with updated Project or errors
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']},
                message="Project not found"
            )

        # Authorization check
        if not project.allows_to(self.user, 'edit_project'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to edit project']},
                message="Not authorized to edit project"
            )

        # Special check for archiving
        if data.active is not None and data.active != project.active:
            if not project.allows_to(self.user, 'archive_project'):
                return ServiceResult.failure_result(
                    errors={'authorization': ['Not authorized to archive project']},
                    message="Not authorized to archive project"
                )

        try:
            # Update fields
            for field, value in data.dict(exclude_unset=True).items():
                setattr(project, field, value)

            project.updated_at = int(datetime.utcnow().timestamp())

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project updated successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error updating project: {str(e)}"
            )

    def archive_project(self, project_id: int) -> ServiceResult:
        """
        Archive project and all subprojects.

        Args:
            project_id: Project ID

        Returns:
            ServiceResult
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']},
                message="Project not found"
            )

        if not project.allows_to(self.user, 'archive_project'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to archive project']},
                message="Not authorized to archive project"
            )

        try:
            # Archive project
            project.active = False
            project.updated_at = int(datetime.utcnow().timestamp())

            # Archive all active children
            for child in project.children:
                if child.active:
                    child.active = False
                    child.updated_at = int(datetime.utcnow().timestamp())

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project archived successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error archiving project: {str(e)}"
            )

    def unarchive_project(self, project_id: int) -> ServiceResult:
        """
        Unarchive project.

        Args:
            project_id: Project ID

        Returns:
            ServiceResult
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']},
                message="Project not found"
            )

        if not project.allows_to(self.user, 'archive_project'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to unarchive project']},
                message="Not authorized to unarchive project"
            )

        try:
            project.active = True
            project.updated_at = int(datetime.utcnow().timestamp())

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project unarchived successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error unarchiving project: {str(e)}"
            )

    def copy_project(
        self,
        source_id: int,
        data: ProjectCreate,
        copy_options: Optional[Dict[str, bool]] = None
    ) -> ServiceResult:
        """
        Copy project with selective data.

        Args:
            source_id: Source project ID
            data: Data for new project
            copy_options: Dict of what to copy (members, modules, etc.)

        Returns:
            ServiceResult with copied Project or errors
        """
        source = self.db.query(Project).get(source_id)
        if not source:
            return ServiceResult.failure_result(
                errors={'source': ['Source project not found']},
                message="Source project not found"
            )

        if not source.allows_to(self.user, 'copy_projects'):
            return ServiceResult.failure_result(
                errors={'authorization': ['Not authorized to copy project']},
                message="Not authorized to copy project"
            )

        copy_options = copy_options or {}

        try:
            # Create new project
            project = Project(**data.dict())

            # Copy settings and status if requested
            if copy_options.get('settings', True):
                project.settings = source.settings.copy() if source.settings else {}

            if copy_options.get('status', False):
                project.status_code = source.status_code
                project.status_explanation = source.status_explanation

            self.db.add(project)
            self.db.flush()

            # Copy modules
            if copy_options.get('modules', True):
                for module in source.enabled_modules:
                    new_module = EnabledModule(project_id=project.id, name=module.name)
                    self.db.add(new_module)
            else:
                # At minimum, enable default modules
                for module_name in DEFAULT_MODULES:
                    new_module = EnabledModule(project_id=project.id, name=module_name)
                    self.db.add(new_module)

            # Copy members
            if copy_options.get('members', False):
                for member in source.members:
                    new_member = Member(user_id=member.user_id, project_id=project.id)
                    self.db.add(new_member)
                    self.db.flush()

                    # Copy only direct roles (not inherited)
                    for mr in member.member_roles:
                        if not mr.inherited_from:
                            new_mr = MemberRole(member_id=new_member.id, role_id=mr.role_id)
                            self.db.add(new_mr)
            else:
                # At minimum, add creator as admin
                self._initialize_project(project)

            self.db.commit()
            self.db.refresh(project)

            return ServiceResult.success_result(
                project,
                message="Project copied successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error copying project: {str(e)}"
            )

    def delete_project(self, project_id: int) -> ServiceResult:
        """
        Delete project (requires admin).

        Args:
            project_id: Project ID

        Returns:
            ServiceResult
        """
        project = self.db.query(Project).get(project_id)
        if not project:
            return ServiceResult.failure_result(
                errors={'project': ['Project not found']},
                message="Project not found"
            )

        # Only admins can delete
        if not self.user.admin:
            return ServiceResult.failure_result(
                errors={'authorization': ['Only admins can delete projects']},
                message="Only admins can delete projects"
            )

        try:
            self.db.delete(project)
            self.db.commit()

            return ServiceResult.success_result(
                message="Project deleted successfully"
            )

        except Exception as e:
            self.db.rollback()
            return ServiceResult.failure_result(
                errors={'error': [str(e)]},
                message=f"Error deleting project: {str(e)}"
            )

    # Private helper methods

    def _can_create_project(self, parent_id: Optional[int]) -> bool:
        """Check if user can create project"""
        if self.user.admin:
            return True

        # Check global permission (would need to be implemented)
        # For now, allow if has parent and has add_subprojects permission
        if parent_id:
            parent = self.db.query(Project).get(parent_id)
            if parent and parent.allows_to(self.user, 'add_subprojects'):
                return True

        return False

    def _initialize_project(self, project: Project):
        """Initialize new project with defaults"""
        # Add creator as admin member
        admin_role = self.db.query(Role).filter_by(name="Project admin").first()

        if not admin_role:
            # Fallback: get first non-builtin role
            admin_role = self.db.query(Role).filter_by(builtin=0).first()

        if admin_role:
            member = Member(user_id=self.user.id, project_id=project.id)
            self.db.add(member)
            self.db.flush()

            member_role = MemberRole(member_id=member.id, role_id=admin_role.id)
            self.db.add(member_role)

        # Enable default modules
        for module_name in DEFAULT_MODULES:
            module = EnabledModule(project_id=project.id, name=module_name)
            self.db.add(module)

    def _update_nested_set_on_create(self, project: Project):
        """
        Update nested set values when creating child project.

        This is a simplified version. For production, consider using
        a library like sqlalchemy-mptt for proper nested set management.
        """
        parent = project.parent
        if not parent:
            return

        # Simple nested set update
        if parent.rgt:
            project.lft = parent.rgt
            project.rgt = parent.rgt + 1

            # Update all affected nodes
            self.db.query(Project).filter(
                Project.lft >= parent.rgt
            ).update({Project.lft: Project.lft + 2}, synchronize_session=False)

            self.db.query(Project).filter(
                Project.rgt >= parent.rgt
            ).update({Project.rgt: Project.rgt + 2}, synchronize_session=False)

            self.db.flush()
        else:
            # Initialize nested set for parent if not set
            parent.lft = 1
            parent.rgt = 4
            project.lft = 2
            project.rgt = 3
            self.db.flush()
