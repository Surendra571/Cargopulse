"""
CargoPulse Phase 16: AI Logistics Coordinator Endpoints
Full REST API supporting conversation creation, message streaming/polling,
tool execution tracking, and human-in-the-loop action approvals.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.ai import (
    AIConversationCreate,
    AIConversationSummary,
    AIConversationDetail,
    SendMessageRequest,
    SendMessageResponse,
    AIMessageResponse,
    ActionApprovalRequest,
    ActionRejectionRequest,
    ActionRecordResponse
)
from app.services.ai.coordinator_service import AICoordinatorService

router = APIRouter()


@router.post("/conversations", response_model=AIConversationSummary, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: AIConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new AI logistics coordinator conversation session.
    """
    conv = await AICoordinatorService.create_conversation(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        title=payload.title,
        shipment_id=payload.shipment_id
    )
    return AIConversationSummary(
        id=conv.id,
        organization_id=conv.organization_id,
        user_id=conv.user_id,
        title=conv.title,
        shipment_id=conv.shipment_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0
    )


@router.get("/conversations", response_model=List[AIConversationSummary])
async def list_conversations(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List AI coordinator conversations for the current user's organization.
    """
    convs = await AICoordinatorService.list_conversations(
        session=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        limit=limit
    )
    return [
        AIConversationSummary(
            id=c.id,
            organization_id=c.organization_id,
            user_id=c.user_id,
            title=c.title,
            shipment_id=c.shipment_id,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages) if hasattr(c, "messages") and c.messages else 0
        )
        for c in convs
    ]


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get full conversation history and tool outputs for a specific conversation.
    """
    conv = await AICoordinatorService.get_conversation(
        session=db,
        conversation_id=conversation_id,
        organization_id=current_user.organization_id
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return AIConversationDetail(
        id=conv.id,
        organization_id=conv.organization_id,
        user_id=conv.user_id,
        title=conv.title,
        shipment_id=conv.shipment_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            AIMessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                sender_type=m.sender_type,
                content=m.content,
                tool_calls=m.tool_calls or [],
                tool_results=m.tool_results or [],
                action_proposal=m.action_proposal,
                created_at=m.created_at
            )
            for m in conv.messages
        ]
    )


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the AI Coordinator, execute required backend tools,
    and receive grounded factual advice or action proposals.
    """
    # Verify conversation exists and belongs to organization
    conv = await AICoordinatorService.get_conversation(
        session=db,
        conversation_id=conversation_id,
        organization_id=current_user.organization_id
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    user_msg, asst_msg, proposal = await AICoordinatorService.process_user_message(
        session=db,
        conversation_id=conversation_id,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        content=payload.content,
        shipment_id_context=payload.shipment_id or conv.shipment_id
    )

    return SendMessageResponse(
        user_message=AIMessageResponse(
            id=user_msg.id,
            conversation_id=user_msg.conversation_id,
            sender_type=user_msg.sender_type,
            content=user_msg.content,
            tool_calls=user_msg.tool_calls or [],
            tool_results=user_msg.tool_results or [],
            action_proposal=user_msg.action_proposal,
            created_at=user_msg.created_at
        ),
        assistant_message=AIMessageResponse(
            id=asst_msg.id,
            conversation_id=asst_msg.conversation_id,
            sender_type=asst_msg.sender_type,
            content=asst_msg.content,
            tool_calls=asst_msg.tool_calls or [],
            tool_results=asst_msg.tool_results or [],
            action_proposal=asst_msg.action_proposal,
            created_at=asst_msg.created_at
        ),
        action_proposal=proposal
    )


@router.post("/actions/{action_id}/approve")
async def approve_action(
    action_id: uuid.UUID,
    payload: ActionApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Human-in-the-loop: Approve and execute a proposed logistics action (e.g. transporter reassignment).
    Requires appropriate operational authorization.
    """
    result = await AICoordinatorService.approve_action(
        session=db,
        action_id=action_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        approval_notes=payload.reason
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to approve action")
        )
    return result


@router.post("/actions/{action_id}/reject")
async def reject_action(
    action_id: uuid.UUID,
    payload: ActionRejectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Human-in-the-loop: Reject a proposed logistics action with an explanatory reason.
    """
    result = await AICoordinatorService.reject_action(
        session=db,
        action_id=action_id,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        rejection_reason=payload.rejection_reason
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to reject action")
        )
    return result
