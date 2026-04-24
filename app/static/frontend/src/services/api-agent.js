const HOST = "http://localhost:18000";

async function agentRequest(path, options = {}) {
  const { method = "GET", body = null } = options;
  const url = HOST + path;
  const fetchOptions = { method, headers: {} };
  if (body !== null && body !== undefined) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(body);
  }
  const resp = await fetch(url, fetchOptions);
  return resp;
}

async function jsonRequest(path, options = {}) {
  const resp = await agentRequest(path, options);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || data.errmsg || "请求失败");
  }
  return data;
}

export async function teacherReply(payload = {}) {
  return jsonRequest('/api/agent/reply', { method: 'POST', body: payload });
}

export async function buildAgentIndex(payload = {}) {
  return jsonRequest('/api/agent/build-index', { method: 'POST', body: payload });
}

export async function getPrompt(filename) {
  const resp = await agentRequest(`/api/agent/prompt/${filename}`);
  if (!resp.ok) throw new Error("加载失败");
  return resp.text();
}

export async function savePrompt(filename, content) {
  return jsonRequest('/api/agent/prompt/save', { method: 'POST', body: { filename, content } });
}

export async function loadHistoryByFilename(filename) {
  return jsonRequest(`/chat/archive/group-module/${encodeURIComponent(filename)}`);
}