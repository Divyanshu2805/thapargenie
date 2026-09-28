// Merges the saved active branch with the answer being streamed right now.

const PHASE_STATUS = { streaming: 'streaming', done: 'complete', stopped: 'stopped', error: 'failed' };

export function hasStreamingMessage(messages) {
  return (messages || []).some((message) => message.status === 'streaming');
}

// The saved thread can already hold the turn being streamed (a fetch that lands after the
// server saved the question), so drop it here or it would show twice.
function withoutLiveTurn(messages, stream) {
  const regenerating = stream.anchor.kind === 'regenerate';
  // A regenerated answer reuses the saved question, which must stay.
  const liveIds = new Set(
    [regenerating ? null : stream.meta?.user_message_id, stream.meta?.assistant_message_id].filter(Boolean),
  );
  let rest = messages.filter((message) => !liveIds.has(message.id));
  if (!stream.meta && rest.at(-1)?.role === 'assistant' && rest.at(-1).status === 'streaming') {
    rest = rest.slice(0, -1);
    const question = rest.at(-1);
    if (!regenerating && question?.role === 'user' && question.content === stream.question) {
      rest = rest.slice(0, -1);
    }
  }
  return rest;
}

export function buildThread(saved, stream) {
  if (!stream || stream.phase === 'idle' || !stream.anchor) return saved || [];

  const { anchor } = stream;
  const messages = withoutLiveTurn(saved || [], stream);
  let base = messages;
  if (anchor.kind === 'edit' || anchor.kind === 'regenerate') {
    const index = messages.findIndex((message) => message.id === anchor.messageId);
    if (index !== -1) base = messages.slice(0, index);
  }

  const live = [...base];
  if (anchor.kind !== 'regenerate') {
    // No id yet: the question is shown as pending and has no actions.
    live.push({ key: 'live-question', id: null, role: 'user', content: stream.question, status: 'complete' });
  }

  const saved_ = stream.message;
  live.push({
    key: 'live-answer',
    ...(saved_ || {}),
    id: saved_?.id ?? null,
    role: 'assistant',
    status: saved_?.status ?? PHASE_STATUS[stream.phase],
    content: saved_?.content ?? stream.text,
    sources: saved_?.sources ?? stream.sources,
    stage: stream.stage,
    stageDetail: stream.stageDetail,
    error: stream.phase === 'error' ? stream.error : null,
  });
  return live;
}
