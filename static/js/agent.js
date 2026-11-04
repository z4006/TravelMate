/* TravelMate AI 助手页（成员 D）：行程规划 + 旅行问答 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;
    var history = [];
    var lastPayload = null;

    function appendBubble(log, role, text) {
        var bubble = ui.el('div', 'chat-bubble ' + (role === 'user' ? 'chat-user' : 'chat-bot'));
        bubble.appendChild(ui.el('p', null, text));
        log.appendChild(bubble);
        log.scrollTop = log.scrollHeight;
        return bubble;
    }

    function showLoginTip(container) {
        container.appendChild(ui.buildState(
            '请先登录',
            '登录后才能使用 AI 助手。',
            '去登录',
            function () {
                window.location.assign(document.body.getAttribute('data-login-url') || '/login');
            }
        ));
    }

    function setupChat() {
        var log = document.querySelector('[data-chat-log]');
        var form = document.querySelector('[data-chat-form]');
        var input = document.querySelector('[data-chat-input]');
        if (!log || !form || !input) {
            return;
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var message = (input.value || '').trim();
            if (!message) {
                return;
            }
            input.value = '';
            appendBubble(log, 'user', message);
            var pending = appendBubble(log, 'bot', '正在思考…');

            api.post('/api/agent/chat', { message: message, history: history.slice(-8) })
                .then(function (data) {
                    pending.remove();
                    appendBubble(log, 'bot', data.reply || '（没有收到回复）');
                    history.push({ role: 'user', content: message });
                    history.push({ role: 'assistant', content: data.reply || '' });
                    if (data.model_configured === false) {
                        ui.toast('当前使用规则回复，未配置模型密钥', 'info');
                    }
                })
                .catch(function (error) {
                    pending.remove();
                    if (error.status === 401) {
                        appendBubble(log, 'bot', '请先登录后再使用 AI 助手。');
                        return;
                    }
                    appendBubble(log, 'bot', error.message || 'AI 助手暂时不可用');
                });
        });
    }

    function renderPlan(container, data) {
        ui.clear(container);
        var plan = data.plan || {};
        var head = ui.el('div', 'plan-head');
        head.appendChild(ui.el('h3', 'plan-title', plan.title || 'AI 推荐行程'));
        container.appendChild(head);

        if (plan.summary) {
            container.appendChild(ui.el('p', 'plan-summary', plan.summary));
        }

        (plan.days || []).forEach(function (day) {
            var block = ui.el('div', 'plan-day');
            block.appendChild(ui.el('h4', 'plan-day-title', '第 ' + day.day + ' 天'));
            var list = ui.el('ul', 'plan-items');
            (day.items || []).forEach(function (item) {
                var li = ui.el('li', 'plan-item');
                var link = ui.el('a', null, item.name || ('景点 #' + item.attraction_id));
                link.href = ui.detailUrl(item.attraction_id);
                li.appendChild(link);
                if (item.city) {
                    li.appendChild(ui.el('span', 'plan-city', item.city));
                }
                if (item.note) {
                    li.appendChild(ui.el('span', 'plan-note', item.note));
                }
                list.appendChild(li);
            });
            block.appendChild(list);
            container.appendChild(block);
        });

        var foot = ui.el('div', 'plan-actions');
        var saveBtn = ui.el('button', 'btn btn-primary', '保存为我的行程');
        saveBtn.type = 'button';
        saveBtn.addEventListener('click', function () {
            saveItinerary(saveBtn, data);
        });
        foot.appendChild(saveBtn);
        container.appendChild(foot);
    }

    function saveItinerary(button, data) {
        var payload = data.itinerary_payload;
        if (!payload) {
            return;
        }
        ui.setBusy(button, true, '保存中…');
        api.post('/api/itineraries', payload)
            .then(function () {
                ui.setBusy(button, false);
                ui.toast('已保存到「我的行程」', 'success');
            })
            .catch(function (error) {
                ui.setBusy(button, false);
                if (error.status === 401) {
                    ui.toast('保存行程需要先登录，页面右上角可以注册', 'info');
                    return;
                }
                ui.toast(error.message || '保存失败', 'error');
            });
    }

    function setupPlan() {
        var form = document.querySelector('[data-plan-form]');
        var result = document.querySelector('[data-plan-result]');
        var errorNode = document.querySelector('[data-plan-error]');
        var hint = document.querySelector('[data-agent-hint]');
        if (!form || !result) {
            return;
        }

        api.get('/api/agent/status').then(function (data) {
            if (hint && data && data.configured === false) {
                hint.hidden = false;
                hint.textContent = '当前未配置模型密钥，将使用规则版行程生成。';
            }
        }).catch(function () {
            return;
        });

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var message = (form.querySelector('[name="message"]').value || '').trim();
            var days = parseInt(form.querySelector('[name="days"]').value, 10) || 3;
            var city = (form.querySelector('[name="city"]').value || '').trim();
            var startDate = form.querySelector('[name="start_date"]').value || '';

            if (errorNode) {
                errorNode.textContent = '';
            }
            if (!message) {
                if (errorNode) {
                    errorNode.textContent = '请先描述你的需求';
                }
                return;
            }

            var payload = { message: message, days: days };
            if (city) {
                payload.city = city;
            }
            if (startDate) {
                payload.start_date = startDate;
            }

            var submit = form.querySelector('button[type="submit"]');
            ui.setBusy(submit, true, '生成中…');
            ui.clear(result);
            result.appendChild(ui.el('p', 'plan-summary', '正在生成行程…'));

            api.post('/api/agent/plan', payload).then(function (data) {
                ui.setBusy(submit, false);
                lastPayload = data;
                renderPlan(result, data);
                if (data.source === 'rule') {
                    ui.toast('当前使用规则版行程', 'info');
                }
            }).catch(function (error) {
                ui.setBusy(submit, false);
                ui.clear(result);
                if (error.status === 401) {
                    showLoginTip(result);
                    return;
                }
                result.appendChild(ui.buildState(
                    '生成失败',
                    error.message || '请稍后重试。',
                    '重试',
                    function () {
                        form.dispatchEvent(new Event('submit'));
                    }
                ));
            });
        });
    }

    function showLoginRequired() {
        var log = document.querySelector('[data-chat-log]');
        var result = document.querySelector('[data-plan-result]');
        var chatForm = document.querySelector('[data-chat-form]');
        var planForm = document.querySelector('[data-plan-form]');

        if (chatForm) {
            chatForm.hidden = true;
        }
        if (planForm) {
            planForm.hidden = true;
        }
        if (log) {
            appendBubble(log, 'bot', 'AI 助手需要登录后才能使用，请点击右上角「登录」。');
        }
        if (result) {
            ui.clear(result);
            result.appendChild(ui.buildState(
                '请先登录',
                '使用 AI 助手需要先登录账号。',
                '去登录',
                function () {
                    window.location.assign(
                        document.body.getAttribute('data-login-url') || '/login'
                    );
                }
            ));
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        api.get('/api/user/info').then(function () {
            setupChat();
            setupPlan();
        }).catch(function () {
            showLoginRequired();
        });
    });
})(window, document);
