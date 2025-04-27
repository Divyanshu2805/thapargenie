// Merges the saved active branch with the answer being streamed right now.

const PHASE_STATUS = { streaming: 'streaming', done: 'complete', stopped: 'stopped', error: 'failed' };

export function hasStreamingMessage(messages) {
  return (messages || []).some((message) => message.status === 'streaming');
}

export function buildThread(saved, stream) {
  const messages = saved || [];
  if (!stream || stream.phase === 'idle' || !stream.anchor) return messages;

  const { anchor } = stream;
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
