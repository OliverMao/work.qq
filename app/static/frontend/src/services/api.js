const HOST = "http://8.138.142.246:18000";
// const HOST = "http://localhost:18000";

async function jsonRequest(path, options = {}) {
  return apiRequest(path, options);
}
export async function apiRequest(path, options = {}) {
  const {
    method = "GET",
    query = null,
    body = null,
    headers = {},
  } = options;

  const url = new URL(path, HOST);
  if (query && typeof query === "object") {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === null) {
        return;
      }
      const str = String(value).trim();
      if (!str) {
        return;
      }
      url.searchParams.set(key, str);
    });
  }

  const fetchOptions = {
    method,
    headers: {
      ...headers,
    },
  };

  if (body !== null && body !== undefined) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(body);
  }

  const resp = await fetch(url.toString(), fetchOptions);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.errmsg || "请求失败");
  }
  if (data.errcode !== 0) {
    throw new Error(data.errmsg || "接口返回异常");
  }
  return data;
}

export function pullArchive() {
  return apiRequest("/chat/archive", { method: "POST" });
}

export function listGroupModules(keyword, page = 1, pageSize = 20) {
  return apiRequest("/chat/archive/group-modules", {
    method: "GET",
    query: { keyword },
  });
}

export function getGroupModule(filename) {
  return apiRequest(`/chat/archive/group-module/${encodeURIComponent(filename)}`, {
    method: "GET",
  });
}

export function createRoomBinding(roomid, roomName) {
  return apiRequest("/chat/archive/room-binding", {
    method: "POST",
    body: {
      roomid,
      room_name: roomName,
    },
  });
}

export function updateRoomBinding(roomid, roomName) {
  return apiRequest(`/chat/archive/room-binding/${encodeURIComponent(roomid)}`, {
    method: "PUT",
    body: {
      room_name: roomName,
    },
  });
}

export function deleteRoomBinding(roomid) {
  return apiRequest(`/chat/archive/room-binding/${encodeURIComponent(roomid)}`, {
    method: "DELETE",
  });
}

export function listUserBindings(keyword) {
  return apiRequest("/chat/archive/user-bindings", {
    method: "GET",
    query: { keyword },
  });
}

export function listArchiveUserCandidates(keyword) {
  return apiRequest("/chat/archive/user-candidates", {
    method: "GET",
    query: { keyword },
  });
}

export function autoBindUserNicknames(payload = {}) {
  return apiRequest("/chat/archive/user-bindings/auto-bind", {
    method: "POST",
    body: payload,
  });
}

export function querySingleUserNickname(userId) {
  return apiRequest("/chat/archive/user-bindings/query-one", {
    method: "POST",
    body: {
      user_id: userId,
    },
  });
}

export function createUserBinding(userId, nickname) {
  return apiRequest("/chat/archive/user-binding", {
    method: "POST",
    body: {
      user_id: userId,
      nickname,
    },
  });
}

export function updateUserBinding(userId, nickname) {
  return apiRequest(`/chat/archive/user-binding/${encodeURIComponent(userId)}`, {
    method: "PUT",
    body: {
      nickname,
    },
  });
}

export function deleteUserBinding(userId) {
  return apiRequest(`/chat/archive/user-binding/${encodeURIComponent(userId)}`, {
    method: "DELETE",
  });
}


export async function loadHistoryByFilename(filename) {
  return jsonRequest(`/chat/archive/group-module/${encodeURIComponent(filename)}`);
}


export async function listChats() {
  return jsonRequest('/api/report/chats');
}

export async function generateReport(roomid, chat_name) {
  var body = { roomid: roomid };
  if (chat_name) {
    body.chat_name = chat_name;
  }
  return jsonRequest('/api/report/generate', { method: 'POST', body: body });
}