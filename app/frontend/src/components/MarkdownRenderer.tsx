/**
 * Lightweight markdown renderer — no external dependencies.
 * Handles: headings, bold, italic, code, links, bullets, numbered lists, tables, horizontal rules.
 */

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInline(text: string): string {
  let result = escapeHtml(text);
  // Bold: **text** or __text__
  result = result.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  result = result.replace(/__(.+?)__/g, "<strong>$1</strong>");
  // Italic: *text* or _text_
  result = result.replace(/\*(.+?)\*/g, "<em>$1</em>");
  result = result.replace(/(?<!\w)_(.+?)_(?!\w)/g, "<em>$1</em>");
  // Inline code: `code`
  result = result.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>');
  // Links: [text](url)
  result = result.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener" class="md-link">$1</a>'
  );
  return result;
}

function renderMarkdown(markdown: string): string {
  const lines = markdown.split("\n");
  const html: string[] = [];
  let inCodeBlock = false;
  let codeContent: string[] = [];
  let inTable = false;
  let tableRows: string[][] = [];
  let inList = false;
  let listType: "ul" | "ol" = "ul";

  const flushList = () => {
    if (inList) {
      html.push(`</${listType}>`);
      inList = false;
    }
  };

  const flushTable = () => {
    if (inTable && tableRows.length > 0) {
      let tableHtml = '<div class="md-table-wrap"><table class="md-table"><thead><tr>';
      const headers = tableRows[0];
      for (const h of headers) {
        tableHtml += `<th>${renderInline(h.trim())}</th>`;
      }
      tableHtml += "</tr></thead><tbody>";
      // Skip separator row (index 1 if it's ---) and render data rows
      const startIdx = tableRows.length > 1 && tableRows[1].every((c) => /^[\s-:]+$/.test(c)) ? 2 : 1;
      for (let i = startIdx; i < tableRows.length; i++) {
        tableHtml += "<tr>";
        for (const cell of tableRows[i]) {
          tableHtml += `<td>${renderInline(cell.trim())}</td>`;
        }
        tableHtml += "</tr>";
      }
      tableHtml += "</tbody></table></div>";
      html.push(tableHtml);
      tableRows = [];
      inTable = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks
    if (line.trim().startsWith("```")) {
      if (inCodeBlock) {
        html.push(`<pre class="md-pre"><code>${escapeHtml(codeContent.join("\n"))}</code></pre>`);
        codeContent = [];
        inCodeBlock = false;
      } else {
        flushList();
        flushTable();
        inCodeBlock = true;
      }
      continue;
    }
    if (inCodeBlock) {
      codeContent.push(line);
      continue;
    }

    // Table rows
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      flushList();
      const cells = line
        .trim()
        .slice(1, -1)
        .split("|");
      if (!inTable) inTable = true;
      tableRows.push(cells);
      continue;
    } else {
      flushTable();
    }

    // Empty line
    if (!line.trim()) {
      flushList();
      continue;
    }

    // Headings
    const headingMatch = line.match(/^(#{1,4})\s+(.+)/);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length;
      html.push(`<h${level} class="md-h${level}">${renderInline(headingMatch[2])}</h${level}>`);
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}\s*$/.test(line.trim())) {
      flushList();
      html.push('<hr class="md-hr" />');
      continue;
    }

    // Unordered list
    const ulMatch = line.match(/^(\s*)[-*+]\s+(.+)/);
    if (ulMatch) {
      if (!inList || listType !== "ul") {
        flushList();
        html.push('<ul class="md-ul">');
        inList = true;
        listType = "ul";
      }
      html.push(`<li>${renderInline(ulMatch[2])}</li>`);
      continue;
    }

    // Ordered list
    const olMatch = line.match(/^(\s*)\d+[.)]\s+(.+)/);
    if (olMatch) {
      if (!inList || listType !== "ol") {
        flushList();
        html.push('<ol class="md-ol">');
        inList = true;
        listType = "ol";
      }
      html.push(`<li>${renderInline(olMatch[2])}</li>`);
      continue;
    }

    // Regular paragraph
    flushList();
    html.push(`<p class="md-p">${renderInline(line)}</p>`);
  }

  flushList();
  flushTable();

  if (inCodeBlock) {
    html.push(`<pre class="md-pre"><code>${escapeHtml(codeContent.join("\n"))}</code></pre>`);
  }

  return html.join("");
}

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  if (!content) return null;
  return <div className="md-root" dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />;
}
