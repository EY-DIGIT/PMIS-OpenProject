"""Database models package."""
from .user import UserModel
from .project import ProjectModel
from .project_audit_log import ProjectAuditLogModel
from .project_member import ProjectMemberModel
from .project_vendor import ProjectVendorModel
from .role import RoleModel
from .work_package import WorkPackageModel
from .work_package_type import WorkPackageTypeModel
from .meeting import MeetingModel
from .meeting_participant import MeetingParticipantModel
from .meeting_agenda_item import MeetingAgendaItemModel
from .milestone import MilestoneModel
from .milestone_vendor import MilestoneVendorModel
from .activity import ActivityModel
from .activity_dependency import ActivityDependencyModel
from .activity_resource import ActivityResourceModel
from .task import TaskModel
from .task_dependency import TaskDependencyModel
from .task_resource import TaskResourceModel
from .subtask import SubtaskModel
from .subtask_dependency import SubtaskDependencyModel
from .subtask_resource import SubtaskResourceModel
from .vendor import VendorModel
from .resource_type import ResourceTypeModel
from .revoked_token import RevokedTokenModel
from .project_status_transition import ProjectStatusTransitionModel
# ProjectOwnerModel was removed in doc 20 — the project_owners whitelist
# was already dead since doc 18 made project.owner a strict division code.
from .comment import CommentModel
from .attachment import AttachmentModel
from .division import DivisionModel

__all__ = [
    "UserModel", "ProjectModel", "ProjectAuditLogModel",
    "ProjectMemberModel", "ProjectVendorModel",
    "RoleModel",
    "WorkPackageModel", "WorkPackageTypeModel", "MeetingModel",
    "MeetingParticipantModel", "MeetingAgendaItemModel",
    "MilestoneModel", "MilestoneVendorModel",
    "ActivityModel", "ActivityDependencyModel", "ActivityResourceModel",
    "TaskModel", "TaskDependencyModel", "TaskResourceModel",
    "SubtaskModel", "SubtaskDependencyModel", "SubtaskResourceModel",
    "VendorModel", "ResourceTypeModel",
    "RevokedTokenModel",
    "ProjectStatusTransitionModel",
    "CommentModel",
    "AttachmentModel",
    "DivisionModel",
]
