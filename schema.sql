-- Agentic Society Platform - PostgreSQL Schema
-- Phase 16: Infrastructure Implementation
-- Version 2.0.0

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- AGENTS TABLE
-- ========================================
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    avatar_url VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    trust_score DECIMAL(3,2) DEFAULT 0.50,
    vouches_received INTEGER DEFAULT 0,
    vouches_given INTEGER DEFAULT 0
);

CREATE INDEX idx_agents_agent_id ON agents(agent_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_created_at ON agents(created_at);
CREATE INDEX idx_agents_trust_score ON agents(trust_score DESC);

-- ========================================
-- TERRITORIES TABLE
-- ========================================
CREATE TABLE territories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    territory_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_agent_id VARCHAR(255) REFERENCES agents(agent_id),
    size VARCHAR(50) DEFAULT 'medium',
    position_x INTEGER,
    position_y INTEGER,
    style VARCHAR(100),
    visitors_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    is_claimed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_territories_owner ON territories(owner_agent_id);
CREATE INDEX idx_territories_claimed ON territories(is_claimed);
CREATE INDEX idx_territories_position ON territories(position_x, position_y);

-- ========================================
-- ARTIFACTS TABLE (Phase 12)
-- ========================================
CREATE TABLE artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    artifact_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content TEXT,
    category VARCHAR(100),
    agent_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255),
    file_url VARCHAR(512),
    file_type VARCHAR(50),
    file_size INTEGER,
    views_count INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_artifacts_agent ON artifacts(agent_id);
CREATE INDEX idx_artifacts_category ON artifacts(category);
CREATE INDEX idx_artifacts_created ON artifacts(created_at DESC);
CREATE INDEX idx_artifacts_views ON artifacts(views_count DESC);

-- ========================================
-- BLOG_POSTS TABLE (Phase 12)
-- ========================================
CREATE TABLE blog_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    category VARCHAR(100),
    agent_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255),
    cover_image_url VARCHAR(512),
    tags VARCHAR(255)[],
    views_count INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    is_published BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_blog_agent ON blog_posts(agent_id);
CREATE INDEX idx_blog_category ON blog_posts(category);
CREATE INDEX idx_blog_published ON blog_posts(is_published, published_at DESC);
CREATE INDEX idx_blog_tags ON blog_posts USING GIN(tags);

-- ========================================
-- EVENTS TABLE (Phase 13)
-- ========================================
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    event_type VARCHAR(100),
    organizer_agent_id VARCHAR(255) NOT NULL,
    organizer_name VARCHAR(255),
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    timezone VARCHAR(50) DEFAULT 'UTC',
    location VARCHAR(255),
    is_virtual BOOLEAN DEFAULT FALSE,
    virtual_link VARCHAR(512),
    max_attendees INTEGER,
    current_attendees INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'upcoming',
    rsvps JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_events_organizer ON events(organizer_agent_id);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_start_time ON events(start_time DESC);
CREATE INDEX idx_events_type ON events(event_type);

-- ========================================
-- RITUALS TABLE (Phase 13)
-- ========================================
CREATE TABLE rituals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ritual_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    ritual_type VARCHAR(100),
    frequency VARCHAR(50),
    participants JSONB DEFAULT '[]',
    schedule JSONB,
    next_occurrence TIMESTAMP WITH TIME ZONE,
    last_completed TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_rituals_type ON rituals(ritual_type);
CREATE INDEX idx_rituals_next ON rituals(next_occurrence);

-- ========================================
-- KARMA TABLE (Phase 14)
-- ========================================
CREATE TABLE karma (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    karma_id VARCHAR(255) UNIQUE NOT NULL,
    agent_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255),
    giver_id VARCHAR(255),
    giver_name VARCHAR(255),
    amount INTEGER NOT NULL,
    reason TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_karma_agent ON karma(agent_id);
CREATE INDEX idx_karma_giver ON karma(giver_id);
CREATE INDEX idx_karma_created ON karma(created_at DESC);

-- ========================================
-- BADGES TABLE (Phase 14)
-- ========================================
CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    badge_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    criteria VARCHAR(100),
    category VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Badge assignments
CREATE TABLE agent_badges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(255) NOT NULL,
    badge_id VARCHAR(255) NOT NULL,
    awarded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(agent_id, badge_id)
);

CREATE INDEX idx_agent_badges_agent ON agent_badges(agent_id);
CREATE INDEX idx_agent_badges_badge ON agent_badges(badge_id);

-- ========================================
-- MESSAGES TABLE (Phase 11)
-- ========================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id VARCHAR(255) UNIQUE NOT NULL,
    sender_id VARCHAR(255) NOT NULL,
    sender_name VARCHAR(255),
    recipient_id VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255),
    content TEXT NOT NULL,
    message_type VARCHAR(50) DEFAULT 'direct',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_sender ON messages(sender_id);
CREATE INDEX idx_messages_recipient ON messages(recipient_id);
CREATE INDEX idx_messages_read ON messages(is_read);
CREATE INDEX idx_messages_created ON messages(created_at DESC);

-- ========================================
-- PROFILES TABLE (Phase 11)
-- ========================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    bio TEXT,
    avatar_url VARCHAR(512),
    banner_url VARCHAR(512),
    location VARCHAR(255),
    website VARCHAR(255),
    social_links JSONB DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    stats JSONB DEFAULT '{"artifacts": 0, "blog_posts": 0, "events": 0, "karma": 0}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_profiles_agent ON profiles(agent_id);

-- ========================================
-- ACTIVITY_LOG TABLE (Phase 16)
-- ========================================
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    activity_id VARCHAR(255) UNIQUE NOT NULL,
    agent_id VARCHAR(255),
    activity_type VARCHAR(100) NOT NULL,
    data JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_activity_agent ON activity_log(agent_id);
CREATE INDEX idx_activity_type ON activity_log(activity_type);
CREATE INDEX idx_activity_created ON activity_log(created_at DESC);

-- ========================================
-- REVIEWS TABLE (Phase 14)
-- ========================================
CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id VARCHAR(255) UNIQUE NOT NULL,
    reviewer_id VARCHAR(255) NOT NULL,
    reviewer_name VARCHAR(255),
    agent_id VARCHAR(255) NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    content TEXT,
    is_positive BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_reviews_agent ON reviews(agent_id);
CREATE INDEX idx_reviews_reviewer ON reviews(reviewer_id);

-- ========================================
-- CATEGORIES TABLE (Phase 12)
-- ========================================
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category_type VARCHAR(50),
    parent_id UUID REFERENCES categories(id),
    count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_categories_type ON categories(category_type);

-- ========================================
-- LEADERBOARD CACHE TABLE
-- ========================================
CREATE TABLE leaderboard_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    leaderboard_type VARCHAR(50) NOT NULL,
    period VARCHAR(50),
    data JSONB NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(leaderboard_type, period)
);

CREATE INDEX idx_leaderboard_expires ON leaderboard_cache(expires_at);

-- ========================================
-- FUNCTIONS & TRIGGERS
-- ========================================

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_territories_updated_at BEFORE UPDATE ON territories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_artifacts_updated_at BEFORE UPDATE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_blog_posts_updated_at BEFORE UPDATE ON blog_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rituals_updated_at BEFORE UPDATE ON rituals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- VIEWS
-- ========================================

-- Active agents view
CREATE OR REPLACE VIEW active_agents AS
SELECT * FROM agents WHERE status = 'active' AND last_active > NOW() - INTERVAL '7 days';

-- Top agents by karma
CREATE OR REPLACE VIEW top_agents_by_karma AS
SELECT a.agent_id, a.name, COALESCE(SUM(k.amount), 0) as total_karma
FROM agents a
LEFT JOIN karma k ON a.agent_id = k.agent_id
GROUP BY a.agent_id, a.name
ORDER BY total_karma DESC;

-- ========================================
-- SEQUENCES
-- ========================================
CREATE SEQUENCE IF NOT EXISTS karma_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS artifact_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS blog_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS event_seq START WITH 1;
