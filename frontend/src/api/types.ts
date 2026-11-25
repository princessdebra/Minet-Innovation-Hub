export interface User { id: number; name: string; initials: string; role: string; permissions?: string[] }
export interface Horizon { id: number; name: string; description: string; short_description: string }
export interface InnovationType { id: number; name: string; short_description: string }
export interface Stage { id: number; name: string; description: string }
export interface Reference {
  horizons: Horizon[]; innovation_types: InnovationType[]; stages: Stage[];
  sources: string[]; horizon_choices: string[]; mentor_areas: string[];
}

export interface ChallengeCardData {
  id: number; title: string; how_might_we: string; source: string; horizon: string; types: string[];
  sponsor: string; status: string; is_illustrative: boolean; is_featured: boolean;
}
export interface RecordCard {
  kind: 'idea' | 'experiment'; key: string; id: number; title: string; stage: string; status: string;
  owner: string; horizon: string | null; types: string[]; next_label: string; next_text: string | null;
  reference_id: string | null; is_draft: boolean;
}
export interface ChallengeDetailData extends ChallengeCardData {
  background: string | null; success_looks_like: string | null;
  my_ideas: RecordCard[]; colleague_idea_count: number;
}
export interface RecordDetail extends RecordCard {
  tag: string; sponsor: string | null; evidence_lines: string[]; resource_decision: string | null;
  review_notes: Record<string, string>; challenge: { id: number; title: string } | null; can_edit: boolean;
  next_decision_date?: string | null;
}
export interface IdeaDetail extends RecordDetail {
  problem: string | null; solution: string | null; expected_value: string | null; evidence: string | null;
  collaborators: string | null; type_ids: number[]; horizon_unsure: boolean;
}

export interface HomeData {
  user: User;
  tiles: {
    ideas: { count: number; items: { title: string; status: string }[] };
    experiments: { count: number; items: { title: string; status: string }[]; next_review: string | null };
    learning: { percent: number; title: string; in_progress_text: string };
    next_actions: { count: number; items: string[] };
  };
  featured_challenge: ChallengeCardData | null;
  challenge_count: number;
}
export interface LeaderEntry {
  user_id: number; name: string; initials: string; rank: number; value: number; is_me: boolean;
}
export interface LeaderboardData {
  tab: 'learning' | 'ideas'; period: string; column_label: string; entries: LeaderEntry[];
  me: { rank: number; name: string; initials: string; value: number; summary: string };
  total: number; note: string;
}
export interface PathCard {
  id: number; title: string; description: string; section: string; badge: string; footer: string;
  cta: string; percent: number; status: 'not_started' | 'in_progress' | 'completed';
  modules_done: number; modules_total: number; recommended_for: string | null;
}
export interface PathDetailData extends PathCard {
  linked_experiment: { id: number; title: string } | null;
  modules: { id: number; title: string; summary: string | null; minutes: number; done: boolean }[];
}
export interface LearningData {
  continue: PathCard | null; recommended: PathCard[]; next: PathCard[];
  types: InnovationType[]; mentor_areas: string[]; community: { joined: boolean; member_count: number };
}
export interface ImpactData {
  strip: { key: string; label: string; value: number | null }[];
  horizons: { id: number; name: string; headline: string;
    metrics: { id: number; name: string; status: string; evidence_status: string; validated: boolean }[] }[];
  validation: { evidence: string; benefits_owner: string; measurement_period: string; status: string;
    statement: string; validated_count: number; metric_count: number };
  library: { slug: string; title: string; description: string; meta: string; cta: string; count: number }[];
}
export interface SearchResult { type: string; title: string; subtitle: string; path: string }
