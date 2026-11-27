import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Tool Parameter Schemas
# -------------------------------------------------------------

class ToolInvocation(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    data: Any
    error: Optional[str] = None


class ActionProposal(BaseModel):
    action_id: uuid.UUID
    action_type: str
    title: str
    description: str
    confidence_score: float
    requires_approval: bool = True
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = "PENDING"


# -------------------------------------------------------------
# Conversation & Chat Schemas
# -------------------------------------------------------------

class AIConversationCreate(BaseModel):
    title: Optional[str] = None
    shipment_id: Optional[uuid.UUID] = None


class AIMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    content: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    action_proposal: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AIConversationSummary(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    title: str
    shipment_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class AIConversationDetail(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    title: str
    shipment_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    messages: List[AIMessageResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    shipment_id: Optional[uuid.UUID] = None


class SendMessageResponse(BaseModel):
    user_message: AIMessageResponse
    assistant_message: AIMessageResponse
    action_proposal: Optional[ActionProposal] = None


# -------------------------------------------------------------
# Human Approval Schemas
# -------------------------------------------------------------

class ActionApprovalRequest(BaseModel):
    reason: Optional[str] = None


class ActionRejectionRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=1, max_length=1000)


class ActionRecordResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: Optional[uuid.UUID]
    shipment_id: Optional[uuid.UUID]
    action_type: str
    status: str
    prompt_summary: str
    decision_summary: str
    confidence_score: float
    requires_human_approval: bool
    action_payload: Dict[str, Any]
    execution_result: Dict[str, Any]
    rejection_reason: Optional[str]
    rejected_by_user_id: Optional[uuid.UUID]
    rejected_at: Optional[datetime]
    approved_by_user_id: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    initiated_by_user_id: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True
