"""
CargoPulse Phase 16: AI Logistics Coordinator Service
Orchestrates natural language interaction, deterministic tool invocation,
grounded response generation without hallucination, and human approval execution.
"""
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai import AIConversation, AIMessage
from app.models.integrations import AIActionRecord, AuditLog
from app.models.shipment import Shipment, TransporterBooking, ShipmentAssignment
from app.models.transporter import Transporter
from app.models.enums import BookingStatus, ShipmentStatus, AssignmentStatus
from app.schemas.ai import ActionProposal
from app.services.ai import tools


class AICoordinatorService:
    """
    Coordinates AI interactions, tool calling, factual query routing,
    and secure human-in-the-loop approvals.
    """

    @staticmethod
    async def create_conversation(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        title: Optional[str] = None,
        shipment_id: Optional[uuid.UUID] = None
    ) -> AIConversation:
        """Create a new AI conversation session."""
        conv = AIConversation(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            title=title or f"Logistics Investigation - {datetime.now(timezone.utc).strftime('%b %d, %H:%M')}",
            shipment_id=shipment_id
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return conv

    @staticmethod
    async def list_conversations(
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 30
    ) -> List[AIConversation]:
        """List active conversations for an organization."""
        query = select(AIConversation).options(
            selectinload(AIConversation.messages)
        ).where(
            AIConversation.organization_id == organization_id,
            AIConversation.is_deleted == False
        ).order_by(desc(AIConversation.updated_at)).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_conversation(
        session: AsyncSession,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID
    ) -> Optional[AIConversation]:
        """Retrieve full conversation details with messages."""
        query = select(AIConversation).options(
            selectinload(AIConversation.messages)
        ).where(
            AIConversation.id == conversation_id,
            AIConversation.organization_id == organization_id,
            AIConversation.is_deleted == False
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def process_user_message(
        cls,
        session: AsyncSession,
        conversation_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        content: str,
        shipment_id_context: Optional[uuid.UUID] = None
    ) -> Tuple[AIMessage, AIMessage, Optional[ActionProposal]]:
        """
        Process user message, determine tool calls, execute them against live DB,
        synthesize grounded factual response, and propose approvals if needed.
        """
        # Save user message
        user_msg = AIMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="user",
            content=content,
            tool_calls=[],
            tool_results=[]
        )
        session.add(user_msg)

        # 1. Identify intent & tools to execute
        executed_tool_calls, executed_tool_results, proposed_action = await cls._execute_intent_pipeline(
            session=session,
            organization_id=organization_id,
            user_id=user_id,
            conversation_id=conversation_id,
            user_text=content,
            context_shipment_id=shipment_id_context
        )

        # 2. Synthesize factual response from executed tool results
        response_text = cls._synthesize_grounded_response(
            user_text=content,
            tool_results=executed_tool_results,
            proposed_action=proposed_action
        )

        action_prop_dict = proposed_action.dict() if proposed_action else None

        # 3. Save assistant message
        assistant_msg = AIMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_type="assistant",
            content=response_text,
            tool_calls=executed_tool_calls,
            tool_results=executed_tool_results,
            action_proposal=action_prop_dict
        )
        session.add(assistant_msg)

        # Update conversation timestamp
        conv_res = await session.execute(select(AIConversation).where(AIConversation.id == conversation_id))
        conv = conv_res.scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(user_msg)
        await session.refresh(assistant_msg)

        return user_msg, assistant_msg, proposed_action

    @classmethod
    async def _execute_intent_pipeline(
        cls,
        session: AsyncSession,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        conversation_id: uuid.UUID,
        user_text: str,
        context_shipment_id: Optional[uuid.UUID] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[ActionProposal]]:
        """
        Deterministic intent router that invokes real CargoPulse backend tools.
        Guaranteed to work even during LLM provider outages.
        """
        tool_calls = []
        tool_results = []
        action_proposal = None
        lower = user_text.lower()

        # Extract UUIDs or tracking numbers if present
        uuid_matches = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', user_text, re.I)
        tracking_matches = re.findall(r'TRK-[A-Z0-9]+', user_text, re.I)
        extracted_shipment_ref = None
        if uuid_matches:
            extracted_shipment_ref = uuid_matches[0]
        elif tracking_matches:
            extracted_shipment_ref = tracking_matches[0]
        elif context_shipment_id:
            extracted_shipment_ref = str(context_shipment_id)

        # 1. Question: Overdue / missed pickup deadlines
        if "missed pickup" in lower or "overdue pickup" in lower or "missed pickup deadline" in lower or "pickup overdue" in lower:
            tool_calls.append({"tool_name": "list_overdue_pickups", "arguments": {"limit": 10}})
            res = await tools.list_overdue_pickups(session, organization_id, limit=10)
            tool_results.append({"tool_name": "list_overdue_pickups", "success": True, "data": res})

        # 2. Question: Critical or open exceptions
        if "exception" in lower or "critical issue" in lower or "critical alert" in lower:
            severity = "CRITICAL" if "critical" in lower else None
            priority = "HIGH" if "high priority" in lower else None
            tool_calls.append({"tool_name": "get_open_exceptions", "arguments": {"severity": severity, "priority": priority, "limit": 10}})
            res = await tools.get_open_exceptions(session, organization_id, severity=severity, priority=priority, limit=10)
            tool_results.append({"tool_name": "get_open_exceptions", "success": True, "data": res})

        # 3. Question: Replacement transporter / find eligible
        if "replacement" in lower or "replace transporter" in lower or "suitable as a replacement" in lower or "eligible transporter" in lower:
            if extracted_shipment_ref:
                tool_calls.append({"tool_name": "find_eligible_transporters", "arguments": {"shipment_id": extracted_shipment_ref}})
                res = await tools.find_eligible_transporters(session, organization_id, shipment_id=extracted_shipment_ref)
                tool_results.append({"tool_name": "find_eligible_transporters", "success": True, "data": res})

                # Check if reassign proposal was requested
                if "reassign" in lower or "propose" in lower or "request approval" in lower:
                    candidates = res.get("eligible_transporters", [])
                    if candidates:
                        best = candidates[0]
                        tool_calls.append({
                            "tool_name": "request_reassignment_approval",
                            "arguments": {
                                "shipment_id": extracted_shipment_ref,
                                "replacement_transporter_id": best["transporter_id"],
                                "reason": "Operational replacement recommendation"
                            }
                        })
                        prop_res = await tools.request_reassignment_approval(
                            session=session,
                            organization_id=organization_id,
                            shipment_id=extracted_shipment_ref,
                            replacement_transporter_id=best["transporter_id"],
                            reason="Operational recovery recommendation for delayed/missed pickup",
                            additional_cost=50.0,
                            user_id=user_id,
                            conversation_id=conversation_id
                        )
                        tool_results.append({"tool_name": "request_reassignment_approval", "success": prop_res.get("success", False), "data": prop_res})
                        if prop_res.get("success"):
                            action_proposal = ActionProposal(
                                action_id=uuid.UUID(prop_res["action_id"]),
                                action_type="REASSIGN_TRANSPORTER",
                                title=prop_res["proposal"]["title"],
                                description=prop_res["proposal"]["description"],
                                confidence_score=prop_res["proposal"]["confidence_score"],
                                requires_approval=True,
                                payload=prop_res["proposal"],
                                status="PENDING"
                            )
            else:
                # Provide helpful notice
                tool_results.append({
                    "tool_name": "find_eligible_transporters",
                    "success": False,
                    "data": {"message": "Please specify a shipment ID or tracking number to find suitable replacement transporters."}
                })

        # 4. Question: Transporter reliability / performance
        if "reliability" in lower or "performance" in lower or "poor pickup" in lower:
            # Check if transporter name mentioned
            words = user_text.split()
            # If nothing specific mentioned, search top transporters
            t_query = select(Transporter).limit(3)
            t_res = await session.execute(t_query)
            transporters = t_res.scalars().all()
            for t in transporters:
                tool_calls.append({"tool_name": "get_transporter_performance", "arguments": {"transporter_identifier": str(t.id)}})
                t_perf = await tools.get_transporter_performance(session, organization_id, str(t.id))
                tool_results.append({"tool_name": "get_transporter_performance", "success": True, "data": t_perf})

        # 5. Question: Specific shipment status, timeline, why delayed, what happened
        if extracted_shipment_ref and not any(t["tool_name"] == "get_shipment_details" for t in tool_calls):
            if "timeline" in lower or "what happened" in lower or "why" in lower or "delayed" in lower or "status" in lower or "details" in lower:
                tool_calls.append({"tool_name": "get_shipment_details", "arguments": {"shipment_identifier": extracted_shipment_ref}})
                details_res = await tools.get_shipment_details(session, organization_id, extracted_shipment_ref)
                tool_results.append({"tool_name": "get_shipment_details", "success": True, "data": details_res})

                tool_calls.append({"tool_name": "get_shipment_timeline", "arguments": {"shipment_id": extracted_shipment_ref}})
                timeline_res = await tools.get_shipment_timeline(session, organization_id, extracted_shipment_ref)
                tool_results.append({"tool_name": "get_shipment_timeline", "success": True, "data": timeline_res})

        # 6. Question: Reconciliation / POD status
        if "reconciliation" in lower or "pod" in lower or "proof of delivery" in lower:
            if extracted_shipment_ref:
                tool_calls.append({"tool_name": "summarize_reconciliation", "arguments": {"shipment_id": extracted_shipment_ref}})
                rec_res = await tools.summarize_reconciliation(session, organization_id, extracted_shipment_ref)
                tool_results.append({"tool_name": "summarize_reconciliation", "success": True, "data": rec_res})

        # If no specific intent matched, default to checking active exceptions and overdue pickups
        if not tool_calls:
            tool_calls.append({"tool_name": "list_overdue_pickups", "arguments": {"limit": 5}})
            od_res = await tools.list_overdue_pickups(session, organization_id, limit=5)
            tool_results.append({"tool_name": "list_overdue_pickups", "success": True, "data": od_res})

            tool_calls.append({"tool_name": "get_open_exceptions", "arguments": {"limit": 5}})
            exc_res = await tools.get_open_exceptions(session, organization_id, limit=5)
            tool_results.append({"tool_name": "get_open_exceptions", "success": True, "data": exc_res})

        return tool_calls, tool_results, action_proposal

    @classmethod
    def _synthesize_grounded_response(
        cls,
        user_text: str,
        tool_results: List[Dict[str, Any]],
        proposed_action: Optional[ActionProposal] = None
    ) -> str:
        """
        Synthesize natural, informative, strictly factual response from live backend tool data.
        """
        lines = []

        for item in tool_results:
            tool_name = item.get("tool_name")
            data = item.get("data", {})

            if tool_name == "list_overdue_pickups":
                count = data.get("count", 0)
                shipments = data.get("overdue_shipments", [])
                if count == 0:
                    lines.append("Good news: There are currently **no shipments with missed pickup deadlines**.")
                else:
                    lines.append(f"Found **{count} shipment(s)** that have missed pickup deadlines:")
                    for s in shipments:
                        lines.append(f"- **{s['tracking_number']}** ({s['origin_city']} -> {s['destination_city']}): **{s['minutes_overdue']} mins overdue**. Assigned carrier: *{s['assigned_transporter_name']}*.")

            elif tool_name == "get_open_exceptions":
                count = data.get("count", 0)
                exceptions = data.get("exceptions", [])
                if count == 0:
                    lines.append("There are currently **no open operational exceptions** requiring attention.")
                else:
                    lines.append(f"Found **{count} active operational exception(s)**:")
                    for e in exceptions:
                        lines.append(f"- `[{e['severity']} / {e['priority']}]` **{e['exception_type']}**: {e['description']} *(Status: {e['status']})*")

            elif tool_name == "get_shipment_details":
                if not data.get("found"):
                    lines.append(f"Shipment details: {data.get('message')}")
                else:
                    lines.append(f"### Shipment Overview: {data['tracking_number']}")
                    lines.append(f"- **Status**: `{data['status']}`")
                    lines.append(f"- **Route**: {data['origin']['city']} -> {data['destination']['city']}")
                    lines.append(f"- **Cargo**: {data['total_weight_kg']} kg, {data['goods_description']}")
                    lines.append(f"- **Pickup Deadline**: `{data['pickup_deadline']}`")
                    lines.append(f"- **Carrier**: {data['assigned_transporter_name'] or 'None assigned'}")
                    if data.get("is_pickup_overdue"):
                        lines.append("⚠️ **Pickup is marked as OVERDUE!**")

            elif tool_name == "get_shipment_timeline":
                if data.get("found"):
                    events = data.get("events", [])
                    if events:
                        lines.append(f"**Timeline History ({len(events)} events):**")
                        for ev in events[-5:]:  # Show recent events
                            time_str = ev.get('timestamp') or 'Unknown'
                            label = ev.get('event_type') or ev.get('milestone')
                            desc = ev.get('description') or ev.get('notes') or ''
                            lines.append(f"- `{time_str}`: **{label}** - {desc}")
                    else:
                        lines.append("No milestones recorded yet for this shipment.")

            elif tool_name == "find_eligible_transporters":
                if not data.get("found"):
                    lines.append(f"Eligibility search: {data.get('message')}")
                else:
                    candidates = data.get("eligible_transporters", [])
                    lines.append(f"### Recommended Replacement Transporters for {data.get('origin')} -> {data.get('destination')}:")
                    for idx, c in enumerate(candidates, 1):
                        lines.append(f"{idx}. **{c['name']}** - Match Score: `{c['score']:.2f}` (Reliability: {c['pickup_reliability'] * 100:.0f}%, Cost: ${c.get('estimated_cost', 0):.2f})")
                        lines.append(f"   *Rationale: {c.get('explanation')}*")

            elif tool_name == "get_transporter_performance":
                if data.get("found"):
                    lines.append(f"### Carrier Performance: **{data['name']}**")
                    lines.append(f"- **Verification**: `{data['verification_status']}` (Suspended: {data['is_suspended']})")
                    lines.append(f"- **Pickup Reliability**: `{data['pickup_reliability_score'] * 100:.1f}%`")
                    lines.append(f"- **On-Time Delivery**: `{data['on_time_delivery_rate'] * 100:.1f}%`")
                    lines.append(f"- **Acceptance Rate**: `{data['acceptance_rate_pct']}%` across {data['total_bookings']} bookings.")
                    if data.get("missed_pickups", 0) > 0:
                        lines.append(f"⚠️ **Recorded Missed Pickups**: {data['missed_pickups']}")

            elif tool_name == "summarize_reconciliation":
                if data.get("found"):
                    lines.append(f"### Delivery Reconciliation: {data['tracking_number']}")
                    lines.append(f"- **Status**: `{data.get('reconciliation_status') or data.get('status')}`")
                    lines.append(f"- **Quantity Matched**: `{data.get('is_matched')}` (Discrepancy: {data.get('quantity_discrepancy', 0)} units)")
                    if data.get("discrepancy_reason"):
                        lines.append(f"- **Notes**: {data['discrepancy_reason']}")

        if proposed_action:
            lines.append("\n---")
            lines.append("### ⚡ Human Action Required")
            lines.append(f"**Proposal**: {proposed_action.title}")
            lines.append(f"{proposed_action.description}")
            lines.append("Please click **Approve** or **Reject** on the action card below to proceed.")

        return "\n\n".join(lines) if lines else "I have checked your organization records. How else can I assist with your shipments or transporters?"

    @classmethod
    async def approve_action(
        cls,
        session: AsyncSession,
        action_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        approval_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute an approved human action record (e.g. carrier reassignment).
        Enforces tenant isolation, idempotency, and audit logging.
        """
        # Find action record
        query = select(AIActionRecord).where(
            AIActionRecord.id == action_id,
            AIActionRecord.organization_id == organization_id
        )
        res = await session.execute(query)
        action = res.scalar_one_or_none()
        if not action:
            return {"success": False, "error": f"Action record '{action_id}' not found."}

        if action.status == "EXECUTED":
            return {"success": True, "message": "Action was already executed.", "action_id": str(action.id)}
        if action.status == "REJECTED":
            return {"success": False, "error": "Cannot approve a previously rejected action."}

        payload = action.action_payload or {}
        now = datetime.now(timezone.utc)

        execution_result = {}

        if action.action_type == "REASSIGN_TRANSPORTER":
            shipment_id_str = payload.get("shipment_id")
            replacement_t_id_str = payload.get("replacement_transporter_id")
            if not shipment_id_str or not replacement_t_id_str:
                return {"success": False, "error": "Invalid action payload: missing shipment or transporter ID."}

            s_id = uuid.UUID(shipment_id_str)
            t_id = uuid.UUID(replacement_t_id_str)

            # Update shipment assignment
            ship_res = await session.execute(
                select(Shipment).where(Shipment.id == s_id, Shipment.organization_id == organization_id)
            )
            shipment = ship_res.scalar_one_or_none()
            if not shipment:
                return {"success": False, "error": "Target shipment no longer exists."}

            # Update shipment assignment: cancel old active assignments
            assign_res = await session.execute(
                select(ShipmentAssignment).where(
                    ShipmentAssignment.shipment_id == s_id,
                    ShipmentAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.ACCEPTED]),
                    ShipmentAssignment.is_deleted == False,
                )
            )
            for old_assign in assign_res.scalars().all():
                old_assign.status = AssignmentStatus.CANCELLED
                old_assign.cancellation_reason = f"Reassigned to {payload.get('replacement_transporter_name', 'replacement carrier')}"

            # Cancel previous booking if still active
            prev_bkg_res = await session.execute(
                select(TransporterBooking).where(
                    TransporterBooking.shipment_id == s_id,
                    TransporterBooking.status.in_([BookingStatus.REQUESTED, BookingStatus.ACCEPTED, BookingStatus.CONFIRMED]),
                    TransporterBooking.is_deleted == False,
                )
            )
            for prev_bkg in prev_bkg_res.scalars().all():
                prev_bkg.status = BookingStatus.CANCELLED
                prev_bkg.cancellation_reason = "Cancelled due to operational reassignment"

            # Update shipment status
            shipment.status = ShipmentStatus.COMMITTED

            # Create or update booking request for replacement carrier
            booking = TransporterBooking(
                id=uuid.uuid4(),
                shipment_id=s_id,
                transporter_id=t_id,
                organization_id=organization_id,
                status=BookingStatus.REQUESTED,
                expires_at=datetime.now(timezone.utc) + timedelta(days=2),
                response_notes=f"AI Coordinator reassignment approved by operations staff. Reason: {payload.get('reason')}"
            )
            session.add(booking)

            execution_result = {
                "shipment_id": str(s_id),
                "previous_transporter_id": payload.get("current_transporter_id"),
                "new_transporter_id": str(t_id),
                "booking_id": str(booking.id),
                "status": "REASSIGNMENT_EXECUTED",
                "notes": approval_notes
            }

        # Mark action record approved & executed
        action.status = "EXECUTED"
        action.approved_by_user_id = user_id
        action.approved_at = now
        action.execution_result = execution_result

        # Add Audit Log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="AI_ACTION_APPROVED_AND_EXECUTED",
            entity_name="AIActionRecord",
            entity_id=action.id,
            changes={
                "action_type": action.action_type,
                "status": "EXECUTED",
                "execution_result": execution_result
            }
        )
        session.add(audit)

        await session.commit()

        return {
            "success": True,
            "action_id": str(action.id),
            "status": "EXECUTED",
            "execution_result": execution_result
        }

    @classmethod
    async def reject_action(
        cls,
        session: AsyncSession,
        action_id: uuid.UUID,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
        rejection_reason: str
    ) -> Dict[str, Any]:
        """
        Reject an AI action proposal.
        """
        query = select(AIActionRecord).where(
            AIActionRecord.id == action_id,
            AIActionRecord.organization_id == organization_id
        )
        res = await session.execute(query)
        action = res.scalar_one_or_none()
        if not action:
            return {"success": False, "error": f"Action record '{action_id}' not found."}

        if action.status == "EXECUTED":
            return {"success": False, "error": "Cannot reject an action that has already been executed."}

        now = datetime.now(timezone.utc)
        action.status = "REJECTED"
        action.rejection_reason = rejection_reason
        action.rejected_by_user_id = user_id
        action.rejected_at = now

        # Add Audit Log
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            action="AI_ACTION_REJECTED",
            entity_name="AIActionRecord",
            entity_id=action.id,
            changes={
                "action_type": action.action_type,
                "status": "REJECTED",
                "rejection_reason": rejection_reason
            }
        )
        session.add(audit)
        await session.commit()

        return {
            "success": True,
            "action_id": str(action.id),
            "status": "REJECTED",
            "rejection_reason": rejection_reason
        }
