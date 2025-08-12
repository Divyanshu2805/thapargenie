// Download or print one chat. Both use the active branch shown on screen.
import { downloadBlob } from '@/lib/download';

export function chatFilename(title, date = new Date()) {
  const slug = (title || 'chat')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/[\s_-]+/g, '-')
    .slice(0, 60)
    .replace(/-+$/, '');
  return `thapargenie-${slug || 'chat'}-${date.toISOString().slice(0, 10)}.md`;
}

function sourceLine(source) {
  const where = [source.heading_path, source.page_start ? `p. ${source.page_start}` : ''].filter(Boolean).join(', ');
  const label = where ? `${source.title} (${where})` : source.title;
  return /^https:\/\//.test(source.url || '') ? `[${label}](${source.url})` : label;
}

/** The chat as Markdown: the title, when it was exported, then each question and answer. */
export function chatToMarkdown(conversation, messages, now = new Date()) {
  const title = conversation?.title || 'New conversation';
  const lines = [`# ${title}`, '', `_Exported from ThaparGenie on ${now.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}. Answers can be wrong; check the official sources._`];
  for (const message of messages) {
    if (!message.content?.trim()) continue;
    if (message.role === 'user') {
      lines.push('', '---', '', `**You:** ${message.content.trim()}`);
      continue;
    }
    lines.push('', '**ThaparGenie:**', '', message.content.trim());
    const sources = (message.sources || []).filter((source) => source.cited !== false);
    if (sources.length) {
      lines.push('', 'Sources:');
      for (const source of sources) lines.push(`${source.position}. ${sourceLine(source)}`);
    }
  }
  return `${lines.join('\n')}\n`;
}

export function downloadText(text, filename, type = 'text/markdown;charset=utf-8') {
  downloadBlob(new Blob([text], { type }), filename);
}

/** Prints in the light theme, whatever is on screen: dark pages print as light text on white. */
export function printChat() {
  const root = document.documentElement;
  const wasDark = root.classList.contains('dark');
  const restore = () => {
    if (wasDark) root.classList.add('dark');
    window.removeEventListener('afterprint', restore);
  };
  if (wasDark) root.classList.remove('dark');
  window.addEventListener('afterprint', restore);
  window.print();
}
