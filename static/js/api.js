/* TravelMate 接口封装
 * 统一处理：JSON 外壳 {success, message, data}、Session Cookie、CSRF Token、错误码
 * 后端契约（成员 A）：GET /api/csrf-token 返回 data.csrf_token；
 * 写操作需要 X-CSRF-Token 请求头；登录/退出会重建 Session，需要重新获取 Token。
 */
(function (window) {
    'use strict';

    var CSRF_ENDPOINT = '/api/csrf-token';
    var DEFAULT_MESSAGES = {
        400: '请求参数错误',
        401: '请先登录',
        403: '没有访问权限',
        404: '请求的资源不存在',
        405: '请求方法不被允许',
        409: '数据冲突，请勿重复提交',
        429: '操作过于频繁，请稍后再试',
        500: '服务器内部错误'
    };

    var csrfToken = null;
    var csrfTask = null;

    function ApiError(message, status, payload) {
        Error.call(this, message);
        this.name = 'ApiError';
        this.message = message || '请求失败';
        this.status = status || 0;
        this.payload = payload || null;
    }
    ApiError.prototype = Object.create(Error.prototype);
    ApiError.prototype.constructor = ApiError;

    function messageFor(response, payload) {
        if (payload && typeof payload.message === 'string' && payload.message) {
            return payload.message;
        }
        return DEFAULT_MESSAGES[response.status] || ('请求失败（HTTP ' + response.status + '）');
    }

    // 按后端实际返回结构读取 Token，兼容 data.csrf_token 与顶层字段
    function readCsrf(payload) {
        if (!payload || typeof payload !== 'object') {
            return null;
        }
        var candidates = [payload.csrf_token, payload.token];
        if (payload.data && typeof payload.data === 'object') {
            candidates.push(payload.data.csrf_token, payload.data.token);
        }
        for (var i = 0; i < candidates.length; i += 1) {
            if (typeof candidates[i] === 'string' && candidates[i]) {
                return candidates[i];
            }
        }
        return null;
    }

    function refreshCsrfToken() {
        if (csrfTask) {
            return csrfTask;
        }
        csrfTask = window.fetch(CSRF_ENDPOINT, {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { Accept: 'application/json' }
        }).then(function (response) {
            return response.json().catch(function () {
                return null;
            }).then(function (payload) {
                if (!response.ok || !payload || payload.success === false) {
                    throw new ApiError(messageFor(response, payload), response.status, payload);
                }
                var token = readCsrf(payload);
                if (!token) {
                    throw new ApiError('获取 CSRF Token 失败：响应中缺少 csrf_token', response.status, payload);
                }
                csrfToken = token;
                return token;
            });
        }).catch(function (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            throw new ApiError('无法获取 CSRF Token，请确认 Flask 服务已启动', 0, null);
        }).then(function (token) {
            csrfTask = null;
            return token;
        }, function (error) {
            csrfTask = null;
            throw error;
        });
        return csrfTask;
    }

    function ensureCsrfToken() {
        return csrfToken ? Promise.resolve(csrfToken) : refreshCsrfToken();
    }

    function buildUrl(path, query) {
        var url = path;
        if (!query) {
            return url;
        }
        var parts = [];
        Object.keys(query).forEach(function (key) {
            var value = query[key];
            if (value === undefined || value === null || value === '') {
                return;
            }
            parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value));
        });
        if (!parts.length) {
            return url;
        }
        return url + (url.indexOf('?') === -1 ? '?' : '&') + parts.join('&');
    }

    function request(path, options) {
        var config = options || {};
        var method = (config.method || 'GET').toUpperCase();
        var isWrite = method !== 'GET' && method !== 'HEAD';
        var hasBody = config.body !== undefined && config.body !== null;
        var retried = false;

        function send() {
            return ensureCsrfToken().then(function (token) {
                var headers = { Accept: 'application/json' };
                if (hasBody) {
                    headers['Content-Type'] = 'application/json';
                }
                if (isWrite && token) {
                    headers['X-CSRF-Token'] = token;
                }
                return window.fetch(buildUrl(path, config.query), {
                    method: method,
                    headers: headers,
                    credentials: 'same-origin',
                    cache: 'no-store',
                    body: hasBody ? JSON.stringify(config.body) : undefined
                });
            }).then(function (response) {
                return response.json().catch(function () {
                    return null;
                }).then(function (payload) {
                    var ok = response.ok && (!payload || payload.success !== false);
                    if (ok) {
                        if (config.raw || !payload) {
                            return payload;
                        }
                        return Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload;
                    }
                    var message = messageFor(response, payload);
                    // CSRF 校验在进入业务逻辑之前完成，刷新 Token 后重试一次不会产生重复数据
                    if (isWrite && response.status === 403 && /csrf/i.test(message) && !retried) {
                        retried = true;
                        csrfToken = null;
                        return refreshCsrfToken().then(send);
                    }
                    throw new ApiError(message, response.status, payload);
                });
            });
        }

        return send().catch(function (error) {
            if (error instanceof ApiError) {
                throw error;
            }
            throw new ApiError('网络连接失败，请确认 Flask 服务已启动', 0, null);
        });
    }

    window.TMApi = {
        request: request,
        get: function (path, query) {
            return request(path, { query: query });
        },
        post: function (path, body, query) {
            return request(path, { method: 'POST', body: body, query: query });
        },
        put: function (path, body, query) {
            return request(path, { method: 'PUT', body: body, query: query });
        },
        patch: function (path, body, query) {
            return request(path, { method: 'PATCH', body: body, query: query });
        },
        refreshCsrfToken: refreshCsrfToken,
        getCsrfToken: function () {
            return csrfToken;
        },
        buildUrl: buildUrl,
        ApiError: ApiError,
        DEFAULT_MESSAGES: DEFAULT_MESSAGES
    };
})(window);
