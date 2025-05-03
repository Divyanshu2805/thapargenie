import { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { cn } from '@/lib/utils';

const CITE_SCHEME = 'cite:';

// Answers sometimes carry small inline LaTeX (`$\ge$ 80%`, `$< 80%$`). Without a maths
// renderer, turn the common symbols into plain text instead of showing the markup.
const LATEX_SYMBOLS = {
  ge: '≥',
  geq: '≥',
  le: '≤',
  leq: '≤',
  neq: '≠',
  ne: '≠',
  times: '×',
  pm: '±',
  approx: '≈',
  rightarrow: '→',
  to: '→',
  cdot: '·',
  div: '÷',
};

export function plainMath(text) {
  return text.replace(/(?<![\\\w])\$([^$\n]{1,30})\$/g, (match, body) => {
    // Only short expressions of numbers, operators and known commands are converted,
    // so prices ("$500 and $600") and real formulas stay as they are.
    if (!/^[\s\d.,%<>=+\-()\\a-z]*$/i.test(body)) return match;
    let unknown = false;
    const converted = body.replace(/\\([a-z]+)/gi, (command, name) => {
      const symbol = LATEX_SYMBOLS[name.toLowerCase()];
      if (!symbol) unknown = true;
      return symbol ?? command;
    });
    if (unknown || /[a-z]{2,}/i.test(converted)) return match;
    return converted.trim();
  });
}

// A grouped citation, `[1, 7]`, is the same as `[1][7]`.
function splitGroupedCitations(text) {
  return text.replace(/(?<!\\)\[(\d{1,2}(?:\s*,\s*\d{1,2})+)\](?!\()/g, (match, list) =>
    list
      .split(',')
      .map((number) => `[${number.trim()}]`)
      .join(''),
  );
}

// `[3]` → a link to `cite:3`, rendered as a citation chip. Skips real links (`[3](…)`),
// link definitions (`[3]: …`) and fenced/inline code. `[1][2]` and `[1, 7]` become two chips.
export function linkCitations(markdown) {
  return markdown
    .split(/(```[\s\S]*?```|`[^`\n]*`)/g)
    .map((part, index) =>
      index % 2 === 1
        ? part
        : splitGroupedCitations(plainMath(part)).replace(/(?<!\\)\[(\d{1,2})\](?!\()(:)?/g, (match, number, colon, offset, text) => {
            // `[3]: url` at the start of a line is a link definition, not a citation.
            const lineStart = text.lastIndexOf('\n', offset - 1) + 1;
            const definition = colon && text.slice(lineStart, offset).trim() === '';
            return definition ? match : `[${number}](${CITE_SCHEME}${number})${colon ?? ''}`;
          }),
    )
    .join('');
}

// Only web links (and our citation scheme) survive; `javascript:`, `data:` and the rest become ''.
export function safeUrl(url) {
  const value = String(url || '').trim();
  if (value.startsWith(CITE_SCHEME)) return /^cite:\d{1,2}$/.test(value) ? value : '';
  try {
    const parsed = new URL(value);
    return ['http:', 'https:', 'mailto:'].includes(parsed.protocol) ? value : '';
  } catch {
    return '';
  }
}

function Markdown({ content, renderCitation, className }) {
  return (
    <div className={cn('answer-prose', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        urlTransform={safeUrl}
        components={{
          a({ href, children }) {
            if (href?.startsWith(CITE_SCHEME)) {
              const position = Number(href.slice(CITE_SCHEME.length));
              return renderCitation ? renderCitation(position) : <sup>[{position}]</sup>;
            }
            if (!href) return <span>{children}</span>;
            return (
              <a href={href} target="_blank" rel="noopener noreferrer nofollow">
                {children}
              </a>
            );
          },
          img({ alt }) {
            // Remote images are never loaded from model output.
            return alt ? <span className="text-muted-foreground">[{alt}]</span> : null;
          },
          table({ children }) {
            return (
              <div className="answer-table">
                <table>{children}</table>
              </div>
            );
          },
        }}
      >
        {linkCitations(content || '')}
      </ReactMarkdown>
    </div>
  );
}

export default memo(Markdown);
