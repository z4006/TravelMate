/* TravelMate 已保存行程页（成员 D）：查看行程、生成文案、删除 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function dateText(value) {
        return value ? value : '未设置';
    }

    function showLoginRequired(container) {
        ui.clear(container);
        container.appendChild(ui.buildState(
            '请先登录',
            '登录后可以查看和管理自己的行程。',
            '去登录',
            function () {
                window.location.assign(document.body.getAttribute('data-login-url') || '/login');
            }
        ));
    }

    function copyText(text) {
        function done() {
            ui.toast('已复制，去小红书粘贴吧', 'success');
        }

        function fallback() {
            var area = document.createElement('textarea');
            area.value = text;
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            try {
                document.execCommand('copy');
                done();
            } catch (error) {
                ui.toast('复制失败，请手动选择文本', 'error');
            }
            document.body.removeChild(area);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done, fallback);
        } else {
            fallback();
        }
    }

    function buildCaptionBox(text) {
        var box = ui.el('div', 'caption-box');
        box.setAttribute('data-caption-box', '1');
        box.appendChild(ui.el('h4', 'caption-title', '📝 分享文案'));

        var body = ui.el('pre', 'caption-text');
        body.textContent = text;
        box.appendChild(body);

        var actions = ui.el('div', 'plan-actions');
        var copyBtn = ui.el('button', 'btn btn-primary btn-sm', '复制文案');
        copyBtn.type = 'button';
        copyBtn.addEventListener('click', function () {
            copyText(text);
        });
        actions.appendChild(copyBtn);
        box.appendChild(actions);
        return box;
    }

    function buildDetailBox(itinerary) {
        var box = ui.el('div', 'itinerary-detail');
        box.setAttribute('data-detail-box', '1');

        var attractions = itinerary.attractions || [];
        if (!attractions.length) {
            box.appendChild(ui.el('p', 'itinerary-notes', '这个行程还没有景点'));
            return box;
        }

        box.appendChild(ui.el('h4', 'caption-title', '🗺️ 行程安排'));
        var list = ui.el('ol', 'plan-items');
        attractions.forEach(function (item) {
            var li = ui.el('li', 'plan-item');
            var link = ui.el('a', null, item.name || ('景点 #' + item.attraction_id));
            link.href = ui.detailUrl(item.attraction_id);
            li.appendChild(link);
            if (item.city) {
                li.appendChild(ui.el('span', 'plan-city', item.city));
            }
            if (item.visit_date) {
                li.appendChild(ui.el('span', 'plan-note', '游玩日期 ' + item.visit_date));
            }
            if (item.notes) {
                li.appendChild(ui.el('span', 'plan-note', item.notes));
            }
            list.appendChild(li);
        });
        box.appendChild(list);
        return box;
    }

    function toggleBox(card, selector, builder) {
        var existing = card.querySelector(selector);
        if (existing) {
            existing.parentNode.removeChild(existing);
            return;
        }
        card.appendChild(builder());
    }

    function generateCaption(card, button, itinerary, reload) {
        ui.setBusy(button, true, '生成中…');
        api.post('/api/itineraries/' + encodeURIComponent(itinerary.id) + '/caption', {})
            .then(function (data) {
                ui.setBusy(button, false);
                ui.toast('文案已生成', 'success');
                var old = card.querySelector('[data-caption-box]');
                if (old) {
                    old.parentNode.removeChild(old);
                }
                card.appendChild(buildCaptionBox(data.caption || ''));
                reload();
            })
            .catch(function (error) {
                ui.setBusy(button, false);
                if (error.status === 409) {
                    ui.toast('这个行程已经生成过文案了', 'info');
                    reload();
                    return;
                }
                ui.toast(error.message || '生成文案失败', 'error');
            });
    }

    function removeItinerary(id, button, reload) {
        if (!window.confirm('确定要删除这个行程吗？删除后文案也会一起移除。')) {
            return;
        }
        ui.setBusy(button, true, '删除中…');
        api.request('/api/itineraries/' + encodeURIComponent(id), { method: 'DELETE' })
            .then(function () {
                ui.toast('行程已删除', 'success');
                reload();
            })
            .catch(function (error) {
                ui.setBusy(button, false);
                ui.toast(error.message || '删除失败', 'error');
            });
    }

    /* ---------- 旅行人格鉴定（纯前端统计，不依赖后端） ---------- */

    // 从 price 相关字段里用正则提取数字；ticket_price_cents 为分，需除以 100
    function parsePriceNumber(value) {
        if (typeof value === 'number' && isFinite(value)) {
            return value;
        }
        if (typeof value === 'string') {
            var match = value.match(/\d+(?:\.\d+)?/);
            if (match) {
                var parsed = parseFloat(match[0]);
                return isFinite(parsed) ? parsed : NaN;
            }
        }
        return NaN;
    }

    function attractionPrice(item) {
        if (!item || typeof item !== 'object') {
            return 0;
        }
        if (typeof item.ticket_price_cents === 'number' && isFinite(item.ticket_price_cents)) {
            return item.ticket_price_cents / 100;
        }
        var candidates = [item.ticket_price, item.price, item.ticket, item.admission];
        for (var i = 0; i < candidates.length; i += 1) {
            var price = parsePriceNumber(candidates[i]);
            if (!isNaN(price)) {
                return price;
            }
        }
        return 0;
    }

    function collectStats(itinerary) {
        var attractions = (itinerary && itinerary.attractions) || [];
        var total = 0;
        attractions.forEach(function (item) {
            total += attractionPrice(item);
        });
        return {
            count: attractions.length,
            total: Math.round(total * 100) / 100
        };
    }

    var PERSONAS = {
        special: {
            name: '纯正特种兵',
            motto: '主打一个来过',
            tone: 'red',
            comment: '景点密集、门票克制，节奏拉满，一天打卡八个地方不是梦。'
        },
        chill: {
            name: '尊享躺平党',
            motto: '主打一个享受',
            tone: 'green',
            comment: '景点不多但舍得花钱，慢慢逛、好好住，讲究的是体验。'
        },
        balanced: {
            name: '均衡旅行家',
            motto: '该冲就冲，该躺就躺',
            tone: 'amber',
            comment: '数量与花费都拿捏得刚刚好，行程张弛有度。'
        }
    };

    // 景点数 >= 5 且门票合计 < 200：特种兵；景点数 <= 3 且门票合计 >= 200：躺平党
    function classifyPersona(stats) {
        if (stats.count >= 5 && stats.total < 200) {
            return PERSONAS.special;
        }
        if (stats.count <= 3 && stats.total >= 200) {
            return PERSONAS.chill;
        }
        return PERSONAS.balanced;
    }

    function moneyText(value) {
        var number = isFinite(value) ? value : 0;
        return number % 1 === 0 ? String(number) : number.toFixed(2);
    }

    function openPersonaDialog(itinerary, stats) {
        var persona = classifyPersona(stats);
        var overlay = ui.el('div', 'share-overlay');
        var dialog = ui.el('div', 'share-dialog persona-dialog');
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.setAttribute('aria-label', '旅行人格鉴定结果');

        dialog.appendChild(ui.el(
            'h3',
            'share-dialog-title',
            '旅行人格鉴定 · ' + (itinerary.title || '我的行程')
        ));

        var badge = ui.el('div', 'persona-badge persona-badge-' + persona.tone);
        var badgeText = ui.el('div', 'persona-badge-text');
        badgeText.appendChild(ui.el('strong', 'persona-badge-name', persona.name));
        badgeText.appendChild(ui.el('span', 'persona-badge-motto', persona.motto));
        badge.appendChild(badgeText);
        dialog.appendChild(badge);

        var summary = ui.el('p', 'persona-summary');
        summary.textContent = '本行程共 ' + stats.count + ' 个景点，门票合计 ¥' + moneyText(stats.total)
            + '。' + persona.comment;
        dialog.appendChild(summary);

        var meta = ui.el('div', 'persona-meta');
        meta.appendChild(ui.el('span', 'persona-meta-item', '景点数 ' + stats.count));
        meta.appendChild(ui.el('span', 'persona-meta-item', '门票合计 ¥' + moneyText(stats.total)));
        meta.appendChild(ui.el('span', 'persona-meta-item', '判定标准 5/200'));
        dialog.appendChild(meta);

        var actions = ui.el('div', 'share-dialog-actions');
        var closeBtn = ui.el('button', 'btn btn-ghost btn-sm', '知道啦');
        closeBtn.type = 'button';
        actions.appendChild(closeBtn);
        dialog.appendChild(actions);

        function close() {
            overlay.remove();
            document.removeEventListener('keydown', onKey);
        }
        function onKey(event) {
            if (event.key === 'Escape') {
                close();
            }
        }
        closeBtn.addEventListener('click', close);
        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) {
                close();
            }
        });
        document.addEventListener('keydown', onKey);

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
        closeBtn.focus();
    }

    function identifyPersona(itinerary) {
        var stats = collectStats(itinerary);
        if (!stats.count) {
            ui.toast('这个行程还没有景点，先去景点详情页点「加入行程」吧', 'info');
            return;
        }
        openPersonaDialog(itinerary, stats);
    }

    function renderList(container, items, reload, countNode) {
        ui.clear(container);
        if (countNode) {
            countNode.textContent = items.length ? '共 ' + items.length + ' 个行程' : '';
        }
        if (!items.length) {
            container.appendChild(ui.buildState(
                '还没有保存的行程',
                '去 AI 助手生成一份行程并点击保存，就会出现在这里。',
                '去 AI 助手',
                function () {
                    window.location.assign('/agent');
                }
            ));
            return;
        }

        items.forEach(function (itinerary) {
            var card = ui.el('article', 'itinerary-card');

            var head = ui.el('div', 'itinerary-head');
            head.appendChild(ui.el('h3', 'itinerary-title', itinerary.title || '未命名行程'));
            card.appendChild(head);

            card.appendChild(ui.el(
                'p',
                'itinerary-meta',
                dateText(itinerary.start_date) + ' ~ ' + dateText(itinerary.end_date)
            ));

            if (itinerary.notes) {
                card.appendChild(ui.el('p', 'itinerary-notes', itinerary.notes));
            }

            var attractions = itinerary.attractions || [];
            if (attractions.length) {
                var tags = ui.el('div', 'tag-list');
                attractions.forEach(function (item) {
                    tags.appendChild(ui.el('span', 'tag', item.name || ('景点 #' + item.attraction_id)));
                });
                card.appendChild(tags);
            }

            var actions = ui.el('div', 'plan-actions');

            var personaBtn = ui.el('button', 'btn btn-primary btn-sm', '鉴定旅行人格');
            personaBtn.type = 'button';
            personaBtn.addEventListener('click', function () {
                identifyPersona(itinerary);
            });
            actions.appendChild(personaBtn);

            var detailBtn = ui.el('button', 'btn btn-ghost btn-sm', '查看行程');
            detailBtn.type = 'button';
            detailBtn.addEventListener('click', function () {
                toggleBox(card, '[data-detail-box]', function () {
                    return buildDetailBox(itinerary);
                });
            });
            actions.appendChild(detailBtn);

            if (itinerary.caption) {
                var viewBtn = ui.el('button', 'btn btn-ghost btn-sm', '查看我的文案');
                viewBtn.type = 'button';
                viewBtn.addEventListener('click', function () {
                    toggleBox(card, '[data-caption-box]', function () {
                        return buildCaptionBox(itinerary.caption);
                    });
                });
                actions.appendChild(viewBtn);
            } else {
                var genBtn = ui.el('button', 'btn btn-primary btn-sm', '生成分享文案');
                genBtn.type = 'button';
                genBtn.addEventListener('click', function () {
                    generateCaption(card, genBtn, itinerary, reload);
                });
                actions.appendChild(genBtn);
            }

            var delBtn = ui.el('button', 'btn btn-ghost btn-sm', '删除行程');
            delBtn.type = 'button';
            delBtn.addEventListener('click', function () {
                removeItinerary(itinerary.id, delBtn, reload);
            });
            actions.appendChild(delBtn);

            card.appendChild(actions);
            container.appendChild(card);
        });
    }

    function load() {
        var container = document.querySelector('[data-itinerary-list]');
        if (!container) {
            return;
        }
        var countNode = document.querySelector('[data-itinerary-count]');

        function reload() {
            ui.showSkeletons(container, 2);
            api.get('/api/itineraries').then(function (payload) {
                renderList(container, ui.extractList(payload).items, reload, countNode);
            }).catch(function (error) {
                if (error.status === 401) {
                    showLoginRequired(container);
                    return;
                }
                ui.clear(container);
                container.appendChild(ui.buildState(
                    '暂时无法加载行程',
                    error.message || '请稍后重试。',
                    '重新加载',
                    reload
                ));
            });
        }

        reload();
    }

    document.addEventListener('DOMContentLoaded', load);
})(window, document);
