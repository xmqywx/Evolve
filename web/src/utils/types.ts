export interface Session {
  id: string;
  pid: number | null;
  cwd: string;
  project: string;
  tty: string | null;
  started_at: string;
  last_active: string;
  status: 'active' | 'idle' | 'finished';
  is_wrapped: boolean;
  alias: string | null;
  color: string | null;
  archived: boolean;
}

export interface Task {
  id: string;
  prompt: string;
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled';
  cwd: string;
  priority: string;
  source: string;
  complexity: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  summary: string | null;
}

export interface ContentBlock {
  type: string;
  text?: string;
  name?: string;        // tool_use name
  input?: unknown;      // tool_use input
  content?: string;     // tool_result content
  thinking?: string;    // thinking block
  tool_use_id?: string;
}

export interface SessionMessage {
  type: string;
  uuid?: string;
  sessionId?: string;
  message?: {
    role?: string;
    content?: string | ContentBlock[];
  };
}

export interface StatusInfo {
  scheduler_remaining: number;
  scheduler_running: boolean;
  active_sessions: number;
}

// Memory types
export interface MemorySearchResult {
  source: 'myagent' | 'claude-mem';
  kind: 'memory' | 'observation' | 'summary';
  content: string;
  score: number;
  vector_score: number;
  keyword_score: number;
  project?: string;
  tags?: string[];
  obs_type?: string;
  title?: string;
  created_at?: string;
  task_id?: string;
  memory_id?: number;
  facts?: string;
  files_modified?: string;
  completed?: string;
  next_steps?: string;
}

export interface Observation {
  id: number;
  source: string;
  kind: string;
  memory_session_id: string;
  project: string;
  type: string;
  title: string;
  subtitle: string;
  narrative: string;
  text: string;
  facts: string;
  concepts: string;
  files_read: string;
  files_modified: string;
  created_at: string;
  created_at_epoch: number;
}

export interface SessionSummary {
  id: number;
  source: string;
  kind: string;
  memory_session_id: string;
  project: string;
  request: string;
  investigated: string;
  learned: string;
  completed: string;
  next_steps: string;
  files_read: string;
  files_edited: string;
  notes: string;
  created_at: string;
  created_at_epoch: number;
}

// Agent Self-Report types (Phase 3)

export interface AgentHeartbeat {
  id: number;
  activity: string;
  description: string | null;
  task_ref: string | null;
  progress_pct: number | null;
  eta_minutes: number | null;
  created_at: string;
}

export interface AgentDeliverable {
  id: number;
  title: string;
  type: string;
  status: string;
  path: string | null;
  summary: string | null;
  repo: string | null;
  value_estimate: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentDiscovery {
  id: number;
  title: string;
  category: string;
  content: string | null;
  actionable: boolean;
  priority: string;
  created_at: string;
}

export interface AgentWorkflow {
  id: number;
  name: string;
  trigger: string;
  steps: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentUpgrade {
  id: number;
  proposal: string;
  reason: string | null;
  risk: string;
  impact: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentReview {
  id: number;
  period: string;
  accomplished: string | null;
  failed: string | null;
  learned: string | null;
  next_priorities: string | null;
  tokens_used: number | null;
  cost_estimate: string | null;
  created_at: string;
}

export interface AgentStats {
  heartbeats: number;
  deliverables: number;
  discoveries: number;
  workflows: number;
  upgrades: number;
  reviews: number;
  pending_upgrades: number;
  deliverables_today: number;
}

export interface MemoryStats {
  myagent: {
    memories: number;
    tasks: number;
  };
  claude_mem: {
    available: boolean;
    total_observations?: number;
    total_sessions?: number;
    total_summaries?: number;
    total_prompts?: number;
    observations_by_type?: Record<string, number>;
    top_projects?: Record<string, number>;
  };
}
