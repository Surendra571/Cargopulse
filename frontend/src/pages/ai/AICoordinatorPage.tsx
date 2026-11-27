import React, { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/context/ToastContext";
import {
  Bot,
  User as UserIcon,
  Send,
  Plus,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  ChevronRight,
  Activity,
  Check,
  X
} from "lucide-react";

interface AIConversation {
  id: string;
  title: string;
  shipment_id?: string;
  created_at: string;
  updated_at: string;
}

interface ActionProposal {
  action_id: string;
  action_type: string;
  title: string;
  description: string;
  confidence_score: number;
  requires_approval: boolean;
  payload: any;
  status: string;
}

interface AIMessage {
  id: string;
  sender_type: "user" | "assistant" | "system";
  content: string;
  tool_calls: Array<{ tool_name: string; arguments: any }>;
  tool_results: Array<{ tool_name: string; success: boolean; data: any }>;
  action_proposal?: ActionProposal | null;
  created_at: string;
}

const QUICK_PROMPTS = [
  "Which shipments have missed pickup deadlines?",
  "Which exceptions are critical?",
  "Which transporter is suitable as a replacement for our delayed shipment?",
  "Which transporters have poor pickup reliability?",
  "What is the current delivery status and POD verification?"
];

export const AICoordinatorPage: React.FC = () => {
  const { toast } = useToast();
  const [conversations, setConversations] = useState<AIConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AIMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [submittingAction, setSubmittingAction] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch conversations list
  useEffect(() => {
    loadConversations();
  }, []);

  // Fetch messages when active conversation changes
  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const loadConversations = async () => {
    try {
      const res: any = await apiClient.get<AIConversation[]>("/api/v1/ai-coordinator/conversations");
      const list = Array.isArray(res) ? res : res?.data || [];
      setConversations(list);
      if (list.length > 0 && !activeConversationId) {
        setActiveConversationId(list[0].id);
      }
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  };

  const loadMessages = async (convId: string) => {
    try {
      const res: any = await apiClient.get<{ messages: AIMessage[] }>(`/api/v1/ai-coordinator/conversations/${convId}`);
      setMessages(res?.messages || res?.data?.messages || []);
    } catch (err) {
      console.error("Failed to load messages:", err);
      toast.error("Could not load conversation history");
    }
  };

  const handleCreateNewConversation = async (promptTitle?: string) => {
    try {
      const res: any = await apiClient.post<AIConversation>("/api/v1/ai-coordinator/conversations", {
        title: promptTitle ? promptTitle.slice(0, 40) + "..." : "New Logistics Session"
      });
      const conv = res?.id ? res : res?.data;
      setConversations([conv, ...conversations]);
      setActiveConversationId(conv.id);
      return conv.id;
    } catch (err) {
      toast.error("Failed to start new conversation");
      return null;
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim() || loading) return;

    let targetConvId = activeConversationId;
    if (!targetConvId) {
      targetConvId = await handleCreateNewConversation(text);
      if (!targetConvId) return;
    }

    const optimisticUserMsg: AIMessage = {
      id: "temp-" + Date.now(),
      sender_type: "user",
      content: text,
      tool_calls: [],
      tool_results: [],
      created_at: new Date().toISOString()
    };

    setMessages((prev) => [...prev, optimisticUserMsg]);
    setInputText("");
    setLoading(true);

    try {
      const res: any = await apiClient.post<{
        user_message: AIMessage;
        assistant_message: AIMessage;
        action_proposal?: ActionProposal;
      }>(`/api/v1/ai-coordinator/conversations/${targetConvId}/messages`, {
        content: text
      });

      const payload = res?.user_message ? res : res?.data;
      // Update message list
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticUserMsg.id),
        payload.user_message,
        payload.assistant_message
      ]);

      // Refresh conversations list to update ordering
      loadConversations();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "AI Coordinator failed to respond");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAction = async (actionId: string) => {
    setSubmittingAction(actionId);
    try {
      await apiClient.post(`/api/v1/ai-coordinator/actions/${actionId}/approve`, {
        reason: "Approved via AI Logistics Coordinator Console"
      });
      toast.success("Action approved and executed successfully!");
      if (activeConversationId) {
        loadMessages(activeConversationId);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to approve action");
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleRejectAction = async (actionId: string) => {
    const reason = window.prompt("Enter reason for rejection:") || "Operator rejected proposal";
    setSubmittingAction(actionId);
    try {
      await apiClient.post(`/api/v1/ai-coordinator/actions/${actionId}/reject`, {
        rejection_reason: reason
      });
      toast.info("Action proposal rejected.");
      if (activeConversationId) {
        loadMessages(activeConversationId);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to reject action");
    } finally {
      setSubmittingAction(null);
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-surface-card text-on-surface overflow-hidden">
      {/* Sidebar: Conversation history */}
      <div className="w-80 border-r border-outline-variant bg-surface flex flex-col">
        <div className="p-4 border-b border-outline-variant flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400">
              <Bot className="w-5 h-5" />
            </div>
            <span className="font-semibold text-on-surface">AI Coordinator</span>
          </div>
          <button
            onClick={() => handleCreateNewConversation()}
            className="p-1.5 text-on-surface-subtle hover:text-white hover:bg-surface-container rounded-lg transition"
            title="New Conversation"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-sm text-on-surface-muted">
              No conversations yet. Start asking questions!
            </div>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => setActiveConversationId(c.id)}
                className={`w-full text-left p-3 rounded-lg text-sm transition flex items-center justify-between ${
                  activeConversationId === c.id
                    ? "bg-indigo-600 text-white font-medium"
                    : "text-on-surface-muted hover:bg-surface-card"
                }`}
              >
                <div className="truncate mr-2">
                  <p className="truncate font-medium">{c.title}</p>
                  <p className={`text-xs mt-0.5 ${activeConversationId === c.id ? "text-indigo-200" : "text-on-surface-muted"}`}>
                    {new Date(c.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
                <ChevronRight className="w-4 h-4 opacity-50 shrink-0" />
              </button>
            ))
          )}
        </div>

        {/* Live Grounding Indicator */}
        <div className="p-3 border-t border-outline-variant bg-surface-card/50 text-xs text-on-surface-subtle flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>Connected to live CargoPulse DB tools</span>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-surface-card">
        {/* Header */}
        <div className="h-14 border-b border-outline-variant px-6 flex items-center justify-between bg-surface-card/80 backdrop-blur">
          <div className="flex items-center space-x-3">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <div>
              <h2 className="font-semibold text-on-surface text-sm">Autonomous Logistics & Recovery Agent</h2>
              <p className="text-xs text-on-surface-subtle">Deterministic tool execution with human-in-the-loop safeguards</p>
            </div>
          </div>
          <div className="flex items-center space-x-2 text-xs bg-surface-container-low px-3 py-1.5 rounded-full border border-outline-strong text-on-surface-muted">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Strict Tenant Isolation</span>
          </div>
        </div>

        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="max-w-2xl mx-auto py-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 text-indigo-400 mx-auto flex items-center justify-center mb-4">
                <Bot className="w-8 h-8" />
              </div>
              <h3 className="text-lg font-bold text-on-surface mb-2">Welcome to the CargoPulse AI Coordinator</h3>
              <p className="text-sm text-on-surface-subtle mb-8">
                Ask questions about overdue pickups, carrier reliability, or request high-impact recovery reassignments with human approval safeguards.
              </p>

              {/* Quick Prompt Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
                {QUICK_PROMPTS.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => handleSendMessage(prompt)}
                    className="p-3.5 bg-surface-container/60 hover:bg-surface-container border border-outline-strong/60 hover:border-indigo-500/50 rounded-xl text-xs text-on-surface-muted transition flex items-start space-x-2.5"
                  >
                    <ArrowRight className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                    <span>{prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={`flex space-x-4 max-w-4xl ${
                  m.sender_type === "user" ? "ml-auto justify-end" : "mr-auto justify-start"
                }`}
              >
                {m.sender_type !== "user" && (
                  <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0 mt-1 shadow-md">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`rounded-2xl p-4 text-sm leading-relaxed ${
                    m.sender_type === "user"
                      ? "bg-indigo-600 text-white rounded-tr-none shadow-md"
                      : "bg-surface-container/90 text-on-surface border border-outline-strong/80 rounded-tl-none shadow-lg"
                  }`}
                >
                  {/* Tool execution badges */}
                  {m.tool_calls && m.tool_calls.length > 0 && (
                    <div className="mb-3 flex flex-wrap gap-1.5 pb-2 border-b border-outline-strong/60">
                      {m.tool_calls.map((t, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-surface-card/60 text-indigo-300 border border-indigo-500/20"
                        >
                          <Activity className="w-3 h-3 mr-1 text-emerald-400" />
                          {t.tool_name}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Message body with basic markdown line breaks */}
                  <div className="whitespace-pre-line space-y-1">
                    {m.content}
                  </div>

                  {/* Human-in-the-loop Action Card */}
                  {m.action_proposal && (
                    <div className="mt-4 p-4 rounded-xl bg-surface-card border-2 border-indigo-500/40 shadow-xl">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2 text-indigo-400 font-semibold text-xs tracking-wide uppercase">
                          <ShieldCheck className="w-4 h-4" />
                          <span>Requires Human Approval</span>
                        </div>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-warning-container0/10 text-amber-400 border border-amber-500/20 font-medium">
                          Confidence: {(m.action_proposal.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <h4 className="font-semibold text-on-surface text-sm mb-1">{m.action_proposal.title}</h4>
                      <p className="text-xs text-on-surface-subtle mb-4">{m.action_proposal.description}</p>

                      <div className="flex items-center space-x-3">
                        <button
                          disabled={submittingAction === m.action_proposal.action_id}
                          onClick={() => handleApproveAction(m.action_proposal!.action_id)}
                          className="px-4 py-2 bg-emerald-600 hover:bg-success-container0 text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition disabled:opacity-50"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Approve & Execute</span>
                        </button>
                        <button
                          disabled={submittingAction === m.action_proposal.action_id}
                          onClick={() => handleRejectAction(m.action_proposal!.action_id)}
                          className="px-4 py-2 bg-surface-container hover:bg-rose-950 text-on-surface-muted hover:text-rose-200 border border-outline-strong hover:border-rose-700/50 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition disabled:opacity-50"
                        >
                          <X className="w-3.5 h-3.5" />
                          <span>Reject</span>
                        </button>
                      </div>
                    </div>
                  )}

                  <div className="mt-2 text-right">
                    <span className="text-[10px] text-on-surface-subtle">
                      {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                </div>

                {m.sender_type === "user" && (
                  <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center text-on-surface-muted shrink-0 mt-1">
                    <UserIcon className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))
          )}

          {loading && (
            <div className="flex items-center space-x-3 text-on-surface-subtle text-sm py-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0 shadow-md">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <div className="flex items-center space-x-2 bg-surface-container px-4 py-2 rounded-2xl border border-outline-strong">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
                <span className="text-xs text-on-surface-muted">Consulting CargoPulse database tools...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-outline-variant bg-surface">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center space-x-3 max-w-4xl mx-auto"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask the AI Coordinator (e.g. Which shipments missed pickup?)..."
              disabled={loading}
              className="flex-1 bg-surface-card border border-outline-strong rounded-xl px-4 py-3 text-sm text-on-surface placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
            />
            <button
              type="submit"
              disabled={loading || !inputText.trim()}
              className="p-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl transition shadow-lg shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
