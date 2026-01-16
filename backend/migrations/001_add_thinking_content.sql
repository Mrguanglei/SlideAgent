-- Migration: Add thinking_content field and shares table
-- Date: 2026-01-15
-- Description:
--   1. Add thinking_content field to search_rounds table to store deep thinking analysis
--   2. Create shares table to replace in-memory share storage (stores conversation_id for complete conversation sharing)

-- 1. Add thinking_content column to search_rounds
ALTER TABLE search_rounds ADD COLUMN IF NOT EXISTS thinking_content TEXT;

-- 2. Create shares table (conversation-based sharing)
CREATE TABLE IF NOT EXISTS shares (
    id BIGSERIAL PRIMARY KEY,
    share_id VARCHAR(36) UNIQUE NOT NULL,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    view_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_share_share_id ON shares(share_id);
CREATE INDEX IF NOT EXISTS idx_share_conversation ON shares(conversation_id);
CREATE INDEX IF NOT EXISTS idx_share_expires ON shares(expires_at);

-- Add comments for documentation
COMMENT ON TABLE shares IS 'PPT分享链接表 - 存储分享的完整对话历史（通过conversation_id）';
COMMENT ON COLUMN search_rounds.thinking_content IS '深度思考内容（最后一轮搜索后的整合分析）';
COMMENT ON COLUMN shares.share_id IS '分享短ID（8位UUID）';
COMMENT ON COLUMN shares.conversation_id IS '对话ID - 分享完整对话历史（包含用户输入、AI思考、搜索结果、任务规划、PPT大纲和最终PPT）';
COMMENT ON COLUMN shares.view_count IS '查看次数';
COMMENT ON COLUMN shares.expires_at IS '过期时间';


