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

const CALL_AGENT_TOOL = {
  name: 'call_agent',
  description: 'Send a prompt to your A2A agent.',
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
    
    // Extract and store context from response for next message
    if (result?.result?.task) {
      contextId = result.result.task.contextId;
      taskId = result.result.task.id;
      console.error(`[bridge] Updated context: taskId=${taskId}, contextId=${contextId}`);
    }
    
    // Extract agent's response text
    if (result?.result?.task?.status?.message?.parts?.[0]?.text) {
      const replyText = result.result.task.status.message.parts[0].text;
      return {
        type: 'text',
        text: replyText,
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

      if (toolName === 'call_agent') {
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
