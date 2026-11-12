#!/usr/bin/env node
// a2a-agent-bridge.js
// Bridges Claude (via MCP stdio) to an A2A Agent v1.0 endpoint
// Sends proper A2A v1.0 messages with full metadata

const readline = require('readline');
const https = require('https');
const http = require('http');
const crypto = require('crypto');

const AGENT_URL = process.env.AGENT_URL;
const API_KEY = process.env.AGENT_API_KEY;
const AUTH_TOKEN = process.env.AGENT_TRANSIT_TOKEN;
const BRIDGE_NAME = 'a2a-agent-bridge';

if (!AGENT_URL) {
  console.error('[bridge] AGENT_URL is not set');
  process.exit(1);
}

let requestCounter = 0;
let contextId = null;
let taskId = null;

// Task states the gateway treats as still running. Anything else is terminal, and
// replaying its taskId on the next message gets us -32602 "terminal state".
const LIVE_TASK_STATES = new Set([
  'TASK_STATE_SUBMITTED',
  'TASK_STATE_WORKING',
  'TASK_STATE_INPUT_REQUIRED',
]);

const CALL_AGENT_TOOL = {
  name: 'github_agent',
  description:
    "Answer questions and act on the user's GitHub account: identity, repositories, " +
    'issues, pull requests and commits. Works through the GitHub MCP server behind an ' +
    "Agent Gateway surface holding the user's delegated GitHub OAuth token. Use this for " +
    'any GitHub question about this user.',
  inputSchema: {
    type: 'object',
    properties: {
      prompt: {
        type: 'string',
        description: 'The prompt or question to send to the agent',
      },
    },
    required: ['prompt'],
  },
};

// Older docs and chats refer to the tool by its original name.
const TOOL_ALIASES = new Set([CALL_AGENT_TOOL.name, 'call_agent']);

// On TASK_STATE_AUTH_REQUIRED the gateway returns the consent links in metadata. The user
// never sees metadata, so fold them into the reply text or they are stranded.
function formatConsentLinks(metadata) {
  const consents = metadata?.consent_required;
  if (!Array.isArray(consents) || consents.length === 0) return '';
  return consents
    .map((c) => {
      const scopes = Array.isArray(c.scopes) ? ` (scopes: ${c.scopes.join(', ')})` : '';
      return `\n\n${c.provider_name || 'Authorization'}${scopes}:\n${c.authorization_url}`;
    })
    .join('');
}

const rl = readline.createInterface({ input: process.stdin });

function generateId() {
  return crypto.randomBytes(4).toString('hex');
}

function getCurrentTimestamp() {
  return new Date().toISOString();
}

async function httpRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const client = urlObj.protocol === 'https:' ? https : http;
    const requestOptions = {
      hostname: urlObj.hostname,
      port: urlObj.port,
      path: urlObj.pathname + urlObj.search,
      method: options.method || 'POST',
      headers: {
        'Content-Type': 'application/json',
        'A2A-Version': '1.0',
        ...options.headers,
      },
    };

    if (API_KEY) {
      requestOptions.headers['x-api-key'] = API_KEY;
    }

    if (AUTH_TOKEN) {
      requestOptions.headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
    }

    const req = client.request(requestOptions, (res) => {
      let body = '';
      res.on('data', (chunk) => (body += chunk));
      res.on('end', () => {
        try {
          resolve({
            status: res.statusCode,
            body: body ? JSON.parse(body) : null,
            rawBody: body,
          });
        } catch (e) {
          resolve({
            status: res.statusCode,
            body: body,
            rawBody: body,
          });
        }
      });
    });

    req.on('error', reject);
    if (options.body) {
      req.write(JSON.stringify(options.body));
    }
    req.end();
  });
}

async function callAgent(prompt) {
  try {
    console.error(`[bridge] Calling agent with: "${prompt}"`);

    // Build proper A2A v1.0 message with full metadata
    const messageId = generateId();
    const payload = {
      jsonrpc: '2.0',
      id: generateId(),
      method: 'SendMessage',
      params: {
        message: {
          messageId: messageId,
          contextId: contextId,  // Include context from previous messages
          taskId: taskId,        // Include task from previous messages
          role: 'ROLE_USER',
          parts: [{ 
            text: prompt 
          }],
          metadata: {
            timestamp: getCurrentTimestamp(),
          },
          extensions: [
            'https://fabric.affinidi.io/extensions/agent-identity-binding/v1'
          ],
        },
      },
    };

    console.error(`[bridge] Payload: ${JSON.stringify(payload)}`);

    const response = await httpRequest(AGENT_URL, {
      method: 'POST',
      body: payload,
    });

    console.error(`[bridge] Response status: ${response.status}`);
    console.error(`[bridge] Response: ${JSON.stringify(response.body)?.substring(0, 500)}`);

    if (response.status >= 400) {
      let errorMessage = `Agent error (HTTP ${response.status})`;
      
      if (response.body?.error?.message) {
        errorMessage = response.body.error.message;
      } else if (response.body?.error) {
        errorMessage = JSON.stringify(response.body.error);
      }

      return { type: 'text', text: errorMessage };
    }

    const result = response.body;

    // JSON-RPC errors come back on HTTP 200, so the status check above misses them.
    if (result?.error) {
      const message = result.error.message || JSON.stringify(result.error);
      console.error(`[bridge] JSON-RPC error: ${message}`);
      taskId = null;  // whatever task we were holding is unusable
      return { type: 'text', text: `Agent error: ${message}` };
    }

    // Extract and store context from response for next message. contextId carries the
    // conversation; taskId is only valid while the task is still running. Holding a
    // finished taskId wedges every later message with "is in terminal state".
    const task = result?.result?.task;
    if (task) {
      contextId = task.contextId;
      taskId = LIVE_TASK_STATES.has(task.status?.state) ? task.id : null;
      console.error(`[bridge] Updated context: state=${task.status?.state} taskId=${taskId}, contextId=${contextId}`);
    }

    // Extract agent's response text
    if (task?.status?.message?.parts?.[0]?.text) {
      const replyText = task.status.message.parts[0].text;
      return {
        type: 'text',
        text: replyText + formatConsentLinks(task.status.message.metadata),
      };
    }

    if (result?.result?.message?.parts?.[0]?.text) {
      return {
        type: 'text',
        text: result.result.message.parts[0].text,
      };
    }

    if (result?.result?.reply) {
      return {
        type: 'text',
        text: result.result.reply,
      };
    }

    if (typeof result === 'object') {
      return {
        type: 'text',
        text: JSON.stringify(result, null, 2),
      };
    }

    return {
      type: 'text',
      text: 'No response from agent',
    };
  } catch (error) {
    console.error(`[bridge] Error: ${error.message}`);
    return {
      type: 'text',
      text: `Failed to call agent: ${error.message}`,
    };
  }
}

function respondJson(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

async function handleMessage(msg) {
  try {
    // Notifications carry no id and must never be answered.
    if (msg.id === undefined || msg.method?.startsWith('notifications/')) {
      return;
    }

    if (msg.method === 'initialize') {
      respondJson({
        jsonrpc: '2.0',
        id: msg.id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: {
            name: BRIDGE_NAME,
            version: '1.0.0',
          },
        },
      });
      return;
    }

    if (msg.method === 'tools/list') {
      respondJson({
        jsonrpc: '2.0',
        id: msg.id,
        result: { tools: [CALL_AGENT_TOOL] },
      });
      return;
    }

    if (msg.method === 'tools/call') {
      const toolName = msg.params?.name;
      const args = msg.params?.arguments || {};

      if (TOOL_ALIASES.has(toolName)) {
        const result = await callAgent(args.prompt);
        respondJson({
          jsonrpc: '2.0',
          id: msg.id,
          result: {
            content: [result],
          },
        });
        return;
      }

      respondJson({
        jsonrpc: '2.0',
        id: msg.id,
        error: {
          code: -32601,
          message: `Unknown tool: ${toolName}`,
        },
      });
      return;
    }

    respondJson({
      jsonrpc: '2.0',
      id: msg.id,
      error: {
        code: -32601,
        message: `Unknown method: ${msg.method}`,
      },
    });
  } catch (error) {
    respondJson({
      jsonrpc: '2.0',
      error: {
        code: -32603,
        message: error.message,
      },
    });
  }
}

rl.on('line', (line) => {
  if (!line.trim()) return;
  try {
    const msg = JSON.parse(line);
    handleMessage(msg);
  } catch (error) {
    console.error('[bridge] Parse error:', error);
  }
});

rl.on('close', () => process.exit(0));
