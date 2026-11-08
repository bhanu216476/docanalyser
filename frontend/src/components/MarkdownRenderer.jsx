import React, { useState } from 'react';
import { Copy, Check, Terminal } from 'lucide-react';
import CitationBadge from './CitationBadge';

/**
 * Custom Markdown and citation renderer for Maddy AI responses.
 * Supports:
 * - Code blocks with language badge and copy-to-clipboard button
 * - Markdown tables
 * - Headings (h1, h2, h3, h4)
 * - Ordered and unordered lists
 * - Blockquotes
 * - Bold, italic, inline code
 * - Interactive CitationBadge pills ([1], [2], etc.)
 */
export default function MarkdownRenderer({
  content = '',
  citations = [],
  activeCitation = null,
  onCitationClick = () => {}
}) {
  const [copiedCodeIdx, setCopiedCodeIdx] = useState(null);

  if (!content) return null;

  const handleCopyCode = (code, idx) => {
    navigator.clipboard.writeText(code).then(() => {
      setCopiedCodeIdx(idx);
      setTimeout(() => setCopiedCodeIdx(null), 2000);
    }).catch(err => {
      console.warn('Failed to copy code: ', err);
    });
  };

  // Inline formatting helper
  const renderInline = (text, keyPrefix = 'inline') => {
    if (!text) return null;

    // Split on code `...`, bold **...**, citation [1], markdown link [text](url)
    const tokenRegex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[\d+\]|\[[^\]]+\]\([^)]+\))/g;
    const parts = text.split(tokenRegex);

    return parts.map((part, i) => {
      const key = `${keyPrefix}-${i}`;
      if (!part) return null;

      // Inline code
      if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
        return (
          <code
            key={key}
            style={{
              backgroundColor: 'rgba(0, 0, 0, 0.08)',
              padding: '2px 6px',
              borderRadius: '4px',
              fontFamily: 'monospace',
              fontSize: '0.9em',
              color: 'var(--ac, #6366F1)'
            }}
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      // Bold
      if (part.startsWith('**') && part.endsWith('**') && part.length > 3) {
        return <strong key={key} style={{ fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
      }

      // Italic
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
        return <em key={key} style={{ fontStyle: 'italic' }}>{part.slice(1, -1)}</em>;
      }

      // Citation badge e.g. [1]
      const citMatch = part.match(/^\[(\d+)\]$/);
      if (citMatch) {
        const citationNum = parseInt(citMatch[1], 10);
        const citationObj = citations.find(c => c.index === citationNum || c.id === citationNum);
        return (
          <CitationBadge
            key={key}
            index={citationNum}
            label={part}
            isActive={activeCitation?.index === citationNum}
            onClick={() => onCitationClick(citationObj || { index: citationNum, text: `Passage reference [${citationNum}]` })}
          />
        );
      }

      // Markdown link [text](url)
      const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        return (
          <a
            key={key}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: 'var(--ac, #6366F1)', textDecoration: 'underline' }}
          >
            {linkMatch[1]}
          </a>
        );
      }

      return <span key={key}>{part}</span>;
    });
  };

  // Block level parser
  const renderBlocks = () => {
    const lines = content.split('\n');
    const elements = [];
    let i = 0;
    let blockCounter = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Fenced Code Block: ```lang
      if (line.trim().startsWith('```')) {
        const lang = line.trim().slice(3).trim() || 'code';
        const codeLines = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        i++; // skip closing ```
        const codeText = codeLines.join('\n');
        const codeIdx = blockCounter++;

        elements.push(
          <div
            key={`code-block-${codeIdx}`}
            style={{
              margin: '12px 0',
              borderRadius: '8px',
              overflow: 'hidden',
              backgroundColor: '#1E1E2E',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '6px 12px',
                backgroundColor: '#181825',
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                color: '#CDD6F4',
                fontSize: '11px',
                fontFamily: 'monospace'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Terminal size={12} style={{ color: '#89B4FA' }} />
                <span>{lang}</span>
              </div>
              <button
                type="button"
                onClick={() => handleCopyCode(codeText, codeIdx)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: copiedCodeIdx === codeIdx ? '#A6E3A1' : '#A6ADC8',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  cursor: 'pointer',
                  fontSize: '11px',
                  padding: '2px 6px',
                  borderRadius: '4px'
                }}
                title="Copy code"
              >
                {copiedCodeIdx === codeIdx ? (
                  <>
                    <Check size={12} />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <pre
              style={{
                margin: 0,
                padding: '12px 14px',
                overflowX: 'auto',
                color: '#CDD6F4',
                fontSize: '12.5px',
                lineHeight: 1.5,
                fontFamily: 'Consolas, Monaco, "Courier New", monospace'
              }}
            >
              <code>{codeText}</code>
            </pre>
          </div>
        );
        continue;
      }

      // Markdown Table: lines starting with '|'
      if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
        const tableLines = [];
        while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
          tableLines.push(lines[i].trim());
          i++;
        }

        if (tableLines.length >= 2) {
          const headerCells = tableLines[0]
            .slice(1, -1)
            .split('|')
            .map(c => c.trim());
          const isDivider = (str) => /^[:\s-]+$/.test(str.replace(/\|/g, '').trim());
          const bodyStartIdx = isDivider(tableLines[1]) ? 2 : 1;
          const bodyRows = tableLines.slice(bodyStartIdx).map(rowStr =>
            rowStr
              .slice(1, -1)
              .split('|')
              .map(c => c.trim())
          );

          elements.push(
            <div
              key={`table-${blockCounter++}`}
              style={{
                overflowX: 'auto',
                margin: '12px 0',
                borderRadius: '6px',
                border: '1px solid var(--bd, rgba(0, 0, 0, 0.1))'
              }}
            >
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '12.5px',
                  textAlign: 'left'
                }}
              >
                <thead>
                  <tr style={{ backgroundColor: 'rgba(0, 0, 0, 0.04)', borderBottom: '1px solid var(--bd, #e2e8f0)' }}>
                    {headerCells.map((cell, cIdx) => (
                      <th key={cIdx} style={{ padding: '8px 12px', fontWeight: 600 }}>
                        {renderInline(cell, `th-${cIdx}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {bodyRows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      style={{
                        borderBottom: rIdx < bodyRows.length - 1 ? '1px solid var(--bd, #f1f5f9)' : 'none',
                        backgroundColor: rIdx % 2 === 1 ? 'rgba(0, 0, 0, 0.02)' : 'transparent'
                      }}
                    >
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} style={{ padding: '8px 12px' }}>
                          {renderInline(cell, `td-${rIdx}-${cIdx}`)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          continue;
        }
      }

      // Headings
      if (line.startsWith('### ')) {
        elements.push(
          <h4
            key={`h3-${blockCounter++}`}
            style={{ margin: '14px 0 6px 0', fontSize: '14.5px', fontWeight: 700, color: 'var(--tx)' }}
          >
            {renderInline(line.slice(4), `h3-${i}`)}
          </h4>
        );
        i++;
        continue;
      }
      if (line.startsWith('## ')) {
        elements.push(
          <h3
            key={`h2-${blockCounter++}`}
            style={{ margin: '16px 0 8px 0', fontSize: '15.5px', fontWeight: 700, color: 'var(--tx)' }}
          >
            {renderInline(line.slice(3), `h2-${i}`)}
          </h3>
        );
        i++;
        continue;
      }
      if (line.startsWith('# ')) {
        elements.push(
          <h2
            key={`h1-${blockCounter++}`}
            style={{ margin: '18px 0 10px 0', fontSize: '17px', fontWeight: 700, color: 'var(--tx)' }}
          >
            {renderInline(line.slice(2), `h1-${i}`)}
          </h2>
        );
        i++;
        continue;
      }

      // Blockquote
      if (line.startsWith('> ')) {
        elements.push(
          <blockquote
            key={`quote-${blockCounter++}`}
            style={{
              margin: '8px 0',
              paddingLeft: '12px',
              borderLeft: '3px solid var(--ac, #6366F1)',
              color: 'var(--mu, #64748B)',
              fontStyle: 'italic',
              fontSize: '13px'
            }}
          >
            {renderInline(line.slice(2), `quote-${i}`)}
          </blockquote>
        );
        i++;
        continue;
      }

      // Unordered list item: - or *
      if (/^[-*]\s+/.test(line.trim())) {
        const listItems = [];
        while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
          listItems.push(lines[i].trim().replace(/^[-*]\s+/, ''));
          i++;
        }
        elements.push(
          <ul
            key={`ul-${blockCounter++}`}
            style={{ margin: '8px 0', paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '4px' }}
          >
            {listItems.map((item, lIdx) => (
              <li key={lIdx} style={{ fontSize: '13.5px', lineHeight: 1.5 }}>
                {renderInline(item, `li-${lIdx}`)}
              </li>
            ))}
          </ul>
        );
        continue;
      }

      // Ordered list item: 1.
      if (/^\d+\.\s+/.test(line.trim())) {
        const listItems = [];
        while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
          listItems.push(lines[i].trim().replace(/^\d+\.\s+/, ''));
          i++;
        }
        elements.push(
          <ol
            key={`ol-${blockCounter++}`}
            style={{ margin: '8px 0', paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '4px' }}
          >
            {listItems.map((item, lIdx) => (
              <li key={lIdx} style={{ fontSize: '13.5px', lineHeight: 1.5 }}>
                {renderInline(item, `oli-${lIdx}`)}
              </li>
            ))}
          </ol>
        );
        continue;
      }

      // Empty line
      if (!line.trim()) {
        i++;
        continue;
      }

      // Normal paragraph
      elements.push(
        <p
          key={`p-${blockCounter++}`}
          style={{ margin: '6px 0', fontSize: '13.5px', lineHeight: 1.6 }}
        >
          {renderInline(line, `p-${i}`)}
        </p>
      );
      i++;
    }

    return elements;
  };

  return <div className="maddy-markdown-container">{renderBlocks()}</div>;
}
