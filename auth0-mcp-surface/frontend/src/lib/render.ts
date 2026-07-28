// Response renderers ported from the original Flask chat app.
// These produce HTML strings that the chat page injects with x-html / innerHTML.

export function escapeHtml(s: unknown): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function highlightJson(obj: unknown): string {
  const str = JSON.stringify(obj, null, 2);
  return str.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) return `<span class="j-key">${match}</span>`;
        return `<span class="j-str">${match}</span>`;
      }
      if (/true|false/.test(match)) return `<span class="j-bool">${match}</span>`;
      if (/null/.test(match)) return `<span class="j-bool">${match}</span>`;
      return `<span class="j-num">${match}</span>`;
    }
  );
}

function renderInlineMarkdown(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
    );
}

function renderRichText(text: string): string {
  const blocks = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
  return blocks
    .map((block) => {
      if (block === '---') return '<hr class="response-divider">';
      return `<p>${renderInlineMarkdown(block).replace(/\n/g, '<br>')}</p>`;
    })
    .join('');
}

function extractChatContent(body: any): string | null {
  if (!body || !body.result || !Array.isArray(body.result.content)) return null;
  const textPart = body.result.content.find(
    (item: any) => item.type === 'text' && item.text
  );
  return textPart ? textPart.text : null;
}

function splitChatContent(rawText: string): { answer: string; metadata: string } {
  const marker = /\n---\nchatId:/;
  const match = rawText.match(marker);
  if (!match || match.index === undefined) {
    return { answer: rawText.trim(), metadata: '' };
  }
  return {
    answer: rawText.slice(0, match.index).trim(),
    metadata: rawText.slice(match.index + 5).trim(),
  };
}

function parseMetadataLines(metadataText: string): { key: string; value: string }[] {
  const lines = metadataText
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);
  const rows: { key: string; value: string }[] = [];
  for (const line of lines) {
    if (line === '-' || line === '---') continue;
    const parts = line.split(/:\s(.+)/);
    if (parts.length >= 3) rows.push({ key: parts[0], value: parts[1] });
    else rows.push({ key: 'detail', value: line });
  }
  return rows;
}

function renderMetadata(metadataText: string): string {
  if (!metadataText) return '';
  const rows = parseMetadataLines(metadataText);
  if (!rows.length) return '';
  return `
    <details class="raw-response">
      <summary>Trace Metadata</summary>
      <div class="meta-list">
        ${rows
      .map(
        (row) =>
          `<div class="meta-row"><div class="meta-key">${escapeHtml(
            row.key
          )}</div><div class="meta-value">${escapeHtml(row.value)}</div></div>`
      )
      .join('')}
      </div>
    </details>`;
}

function renderToolList(body: any): string {
  const tools =
    body && body.result && Array.isArray(body.result.tools) ? body.result.tools : null;
  if (!tools || !tools.length) return '';
  return `
    <div class="response-card">
      <div class="response-title">Available Tools</div>
      <div class="tools-list">
        ${tools
      .map(
        (tool: any) => `
          <div class="tool-card">
            <div class="tool-name">${escapeHtml(tool.name || 'Unnamed tool')}</div>
            <div class="tool-description">${renderInlineMarkdown(
          tool.description || 'No description'
        )}</div>
          </div>`
      )
      .join('')}
      </div>
    </div>`;
}

function renderPrimaryResponse(body: any): string {
  const chatText = extractChatContent(body);
  if (chatText) {
    const parts = splitChatContent(chatText);
    let html = `
      <div class="response-card">
        <div class="response-title">Gateway Chat Response</div>
        <div class="response-text">${renderRichText(parts.answer)}</div>
      </div>`;
    html += renderMetadata(parts.metadata);
    return html;
  }
  return renderToolList(body);
}

// ── Caller Context (Verifiable Presentation) ─────────────────────────────────
function renderCallerContext(vp: any): string {
  try {
    const vc = vp.verifiableCredential;
    if (!vc) return '';
    const wb = vc.credentialSubject && vc.credentialSubject.workloadBinding;
    if (!wb) return '';

    const user = wb.userIdentity || {};
    const agent = wb.agentIdentity || {};
    const intent = wb.intent || {};
    const delegations = wb.delegationAction || [];
    const traceId = wb.traceId || '';

    let html = `<div class="ctx-card">`;
    html += `<div class="ctx-header" onclick="const b=this.nextElementSibling;b.style.display=b.style.display==='none'?'':'none'">`;
    html += `📦 Gateway Caller Context<span class="ctx-badge">Verifiable Presentation</span>`;
    html += `</div><div class="ctx-body">`;

    html += `<div><div class="ctx-section-title">👤 User Identity <span class="ctx-hint indigo">(Google OAuth — Caller Context)</span></div><div class="ctx-grid">`;
    html += `<div class="ctx-field"><div class="lbl">Name</div><div class="val">${escapeHtml(user.name || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Email</div><div class="val">${escapeHtml(user.email || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Subject (sub)</div><div class="val">${escapeHtml(user.sub || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Issuer (iss)</div><div class="val">${escapeHtml(user.iss || '—')}</div></div>`;
    html += `</div></div>`;

    html += `<div><div class="ctx-section-title">⚡ Workload Binding</div><div class="ctx-grid">`;
    html += `<div class="ctx-field"><div class="lbl">Agent Name</div><div class="val">${escapeHtml(agent.name || '—')}</div></div>`;
    html += `<div class="ctx-field"><div class="lbl">Trace ID</div><div class="val">${escapeHtml(traceId)}</div></div>`;
    html += `</div></div>`;

    if (intent.protocol) {
      html += `<div><div class="ctx-section-title">🎯 Intent</div><div class="ctx-grid">`;
      html += `<div class="ctx-field"><div class="lbl">Protocol</div><div class="val">${escapeHtml(intent.protocol)}</div></div>`;
      html += `<div class="ctx-field"><div class="lbl">Method</div><div class="val">${escapeHtml(intent.method || '—')}</div></div>`;
      if (intent.tool)
        html += `<div class="ctx-field full"><div class="lbl">Tool</div><div class="val">${escapeHtml(intent.tool)}</div></div>`;
      html += `</div></div>`;
    }

    if (delegations.length > 0) {
      html += `<div><div class="ctx-section-title">🔐 Credential Delegation <span class="ctx-hint yellow">(Auth0 — Delegated by Gateway)</span></div>`;
      html += `<div class="ctx-chips">`;
      delegations.forEach((d: any) => {
        const cls = d.outcome === 'token_injected' ? '' : 'yellow';
        html += `<div class="ctx-chip ${cls}">🔗 <strong>${escapeHtml(
          d.providerName || d.providerId
        )}</strong> &mdash; <span style="opacity:0.8">${escapeHtml(d.outcome)}</span></div>`;
      });
      html += `</div></div>`;
    }

    html += `</div></div>`;
    return html;
  } catch (e) {
    return '';
  }
}

function renderRawBlock(label: string, body: unknown): string {
  if (!body || Object.keys(body as object).length === 0) return '';
  return `<details class="raw-response"><summary>${label}</summary><div class="json-block">${highlightJson(
    body
  )}</div></details>`;
}

// Was the request denied by the gateway? Distinct from `consent_required`
// (an expected step) — this is a hard "you may not access the upstream" verdict.
function accessDeniedReason(data: any): string | null {
  const body = data && data.body;
  // Consent is not a denial — let the consent card handle it.
  if (body && body.consent_required && body.consent_required.length > 0) return null;

  const status = data && data.status;
  const isDeniedStatus = status === 401 || status === 403;

  // JSON-RPC / gateway error payloads.
  const err =
    (body && (body.error || (body.result && body.result.isError && body.result))) || null;
  const haystacks = [
    typeof data?.error === 'string' ? data.error : '',
    err ? JSON.stringify(err) : '',
  ]
    .join(' ')
    .toLowerCase();
  const looksDenied = /denied|unauthor|forbidden|not permitted|permission|access.*(revoked|refused)/.test(
    haystacks
  );

  if (!isDeniedStatus && !looksDenied) return null;

  // Prefer a human-readable message from the payload.
  if (err && typeof err === 'object') {
    if (typeof (err as any).message === 'string') return (err as any).message;
    if (Array.isArray((err as any).content)) {
      const t = (err as any).content.find((c: any) => c.type === 'text' && c.text);
      if (t) return t.text;
    }
  }
  if (typeof data?.error === 'string') return data.error;
  return 'The Agent Gateway declined access to the upstream MCP server.';
}

/**
 * Build the full HTML for a gateway response bubble.
 * `data` is { status, body, error }, `requestBody` is the outgoing MCP request.
 */
export function renderResponse(data: any, requestBody: unknown): string {
  const body = data.body;
  let html = '';

  // Access denied by the gateway (delegation refused / not permitted).
  const deniedReason = accessDeniedReason(data);
  if (deniedReason) {
    html += `<div class="denied-card">
      <div class="denied-title">🚫 Access Denied</div>
      <p class="denied-desc">Your Google sign-in is valid, but the Agent Gateway did not grant access to the upstream MCP server for this request.</p>
      <div class="denied-reason">${escapeHtml(deniedReason)}</div>
    </div>`;
    html += renderRawBlock('Raw MCP request', requestBody);
    html += renderRawBlock('Raw MCP response', body);
    return html;
  }

  // Consent required — Now handled by automatic popup in chat.astro
  // The consent_required response is intercepted in send()/callGateway() before
  // renderResponse() is called, so this block won't execute during auto-popup flow.
  // Keeping it commented for reference / manual fallback mode.
  /*
  if (body && body.consent_required && body.consent_required.length > 0) {
    const consent = body.consent_required[0];
    const authUrl = consent.authorization_url || '';
    html += `<div class="auth-card">
      <div class="auth-title">🔐 Auth0 Consent Required</div>
      <div class="auth-url">${escapeHtml(authUrl)}</div>
      <p class="auth-desc">The gateway needs your permission to access the upstream service on your behalf via Auth0. Click below to authorise, then retry your request.</p>
      ${
        authUrl
          ? `<a href="${escapeHtml(authUrl)}" target="_blank" rel="noreferrer" class="btn btn-primary auth-btn">Authorise Access ↗</a>`
          : ''
      }
    </div>`;
  }
  */

  // Caller context VP — may be direct or nested in result.content[].text JSON.
  let vpSource: any = null;
  if (body && body.result) {
    if (body.result.verifiableCredential) {
      vpSource = body.result;
    } else if (Array.isArray(body.result.content)) {
      for (const c of body.result.content) {
        if (c.type === 'text' && c.text) {
          try {
            const p = JSON.parse(c.text);
            if (p.verifiableCredential) {
              vpSource = p;
              break;
            }
          } catch (_) {
            /* not JSON */
          }
        }
      }
    }
  }
  if (body && body.verifiableCredential) vpSource = body;
  if (vpSource) html += renderCallerContext(vpSource);

  const primary = renderPrimaryResponse(body);
  if (primary) html += primary;

  html += renderRawBlock('Raw MCP request', requestBody);

  if (body && Object.keys(body).length > 0) {
    html += renderRawBlock('Raw MCP response', body);
  } else if (data.error) {
    html += `<div class="json-block" style="color:#fca5a5">${escapeHtml(data.error)}</div>`;
  }

  return html;
}
