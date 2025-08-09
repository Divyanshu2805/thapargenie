import { Bug, Lightbulb, MessageCircleMore, MessageSquareText } from 'lucide-react';

// Kinds of site feedback; keep in step with `SiteFeedbackKind` in chat/models.py.
export const SITE_FEEDBACK_KINDS = [
  { value: 'suggestion', label: 'Idea or suggestion', hint: 'Something that would make it better', icon: Lightbulb },
  { value: 'problem', label: 'Something isn’t working', hint: 'A bug, an error or a broken page', icon: Bug },
  { value: 'answers', label: 'Answer quality', hint: 'Wrong, outdated or missing information', icon: MessageSquareText },
  { value: 'other', label: 'Something else', hint: 'Anything you want the team to know', icon: MessageCircleMore },
];

export const kindLabel = (value) => SITE_FEEDBACK_KINDS.find((kind) => kind.value === value)?.label || value;

export const MIN_MESSAGE = 10;
export const MAX_MESSAGE = 2000;
