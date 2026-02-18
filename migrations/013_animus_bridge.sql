-- Migration 013: Animus bridge tables
-- Supports Phase 3 Animus integration: identity, enhanced memory, safety audit

-- User profiles for Animus Core Layer identity
CREATE TABLE IF NOT EXISTS user_profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT 'User',
    preferences TEXT,
    boundaries TEXT,
    ethics_config TEXT,
    learning_config TEXT,
    metadata TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_profiles_active ON user_profiles(is_active);

-- Enhanced memory store matching Animus MemoryProvider protocol
-- Supports episodic, semantic, procedural, active memory types
CREATE TABLE IF NOT EXISTS animus_memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    subtype TEXT,
    source TEXT NOT NULL DEFAULT 'stated',
    confidence REAL NOT NULL DEFAULT 1.0,
    tags TEXT,
    metadata TEXT,
    workflow_id TEXT,
    agent_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_animus_mem_type ON animus_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_animus_mem_source ON animus_memories(source);
CREATE INDEX IF NOT EXISTS idx_animus_mem_confidence ON animus_memories(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_animus_mem_workflow ON animus_memories(workflow_id);
CREATE INDEX IF NOT EXISTS idx_animus_mem_agent ON animus_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_animus_mem_accessed ON animus_memories(accessed_at DESC);

-- Safety audit log for SafetyGuard protocol compliance
CREATE TABLE IF NOT EXISTS safety_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    reason TEXT,
    check_type TEXT NOT NULL DEFAULT 'action',
    workflow_id TEXT,
    step_id TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_audit_time ON safety_audit_log(checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_safety_audit_workflow ON safety_audit_log(workflow_id);
CREATE INDEX IF NOT EXISTS idx_safety_audit_allowed ON safety_audit_log(allowed);
