const API_BASE = window.location.origin;

async function apiRequest(path, options) {
    const response = await fetch(`${API_BASE}${path}`, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        const message = payload.detail || `请求失败：${response.status}`;
        throw new Error(message);
    }
    return payload;
}

async function apiPost(path, body) {
    return apiRequest(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
}

async function apiGet(path, params = {}) {
    const query = new URLSearchParams(params).toString();
    const url = query ? `${path}?${query}` : path;
    return apiRequest(url, { method: "GET" });
}

async function submitReport(body) {
    return apiPost("/report/submit", body);
}

async function getUserProgress(userId) {
    return apiGet("/user/progress", { user_id: userId });
}

async function completeScenario(body) {
    return apiPost("/user/complete", body);
}

async function getTheaterTemplates() {
    return apiGet("/theater/templates");
}

async function sendTheaterMessage(body) {
    return apiPost("/theater/chat", body);
}

async function getReviewReport(body) {
    return apiPost("/theater/reveal", body);
}
