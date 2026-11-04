/* TravelMate 我的行程页（成员 D 接入） */
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
            '登录后可以创建和查看自己的行程。',
            '去登录',
            function () {
                window.location.assign(document.body.getAttribute('data-login-url') || '/login');
            }
        ));
    }

    function removeItinerary(id, button, reload) {
        if (!window.confirm('确定要删除这个行程吗？')) {
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

    function copyText(text, done) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
                done(true);
            }).catch(function () {
                done(fallbackCopy(text));
            });
            return;
        }
        done(fallbackCopy(text));
    }

    function fallbackCopy(text) {
        var area = document.createElement('textarea');
        area.value = text;
        area.setAttribute('readonly', 'readonly');
        area.style.position = 'fixed';
        area.style.top = '-1000px';
        document.body.appendChild(area);
        area.select();
        var ok = false;
        try {
            ok = document.execCommand('copy');
        } catch (error) {
            ok = false;
        }
        document.body.removeChild(area);
        return ok;
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

    function openCopyDialog(itinerary, copy) {
        var overlay = ui.el('div', 'share-overlay');
        var dialog = ui.el('div', 'share-dialog');
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');

        var title = ui.el('h3', 'share-dialog-title', '分享文案 · ' + (itinerary.title || '我的行程'));
        dialog.appendChild(title);

        var box = ui.el('textarea', 'share-copy-box');
        box.readOnly = true;
        box.value = copy;
        dialog.appendChild(box);

        var actions = ui.el('div', 'share-dialog-actions');
        var copyBtn = ui.el('button', 'btn btn-primary btn-sm', '一键复制');
        copyBtn.type = 'button';
        copyBtn.addEventListener('click', function () {
            copyText(copy, function (ok) {
                ui.toast(ok ? '文案已复制到剪贴板' : '复制失败，请手动选择文本', ok ? 'success' : 'error');
            });
        });
        actions.appendChild(copyBtn);

        var closeBtn = ui.el('button', 'btn btn-ghost btn-sm', '关闭');
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
        box.focus();
        box.select();
    }

    function generateShareCopy(itinerary, button) {
        ui.setBusy(button, true, '生成中…');
        api.post('/api/itineraries/' + encodeURIComponent(itinerary.id) + '/share-copy', {})
            .then(function (payload) {
                ui.setBusy(button, false);
                var data = (payload && payload.data) || {};
                var copy = data.copy || '';
                if (!copy) {
                    ui.toast('文案生成失败，请稍后重试', 'error');
                    return;
                }
                openCopyDialog(itinerary, copy);
                ui.toast(data.source === 'model' ? 'AI 文案已生成' : '已生成文案（模板版）', 'success');
            })
            .catch(function (error) {
                ui.setBusy(button, false);
                ui.toast(error.message || '文案生成失败', 'error');
            });
    }

    function renderList(container, items, reload) {
        ui.clear(container);
        if (!items.length) {
            container.appendChild(ui.buildState(
                '还没有行程',
                '在上面的表单里创建第一个行程吧。'
            ));
            return;
        }
        items.forEach(function (itinerary) {
            var card = ui.el('article', 'itinerary-card');

            var head = ui.el('div', 'itinerary-head');
            head.appendChild(ui.el('h3', 'itinerary-title', itinerary.title || '未命名行程'));

            var actions = ui.el('div', 'itinerary-actions');
            var persona = ui.el('button', 'btn btn-primary btn-sm', '鉴定旅行人格');
            persona.type = 'button';
            persona.addEventListener('click', function () {
                identifyPersona(itinerary);
            });
            actions.appendChild(persona);

            var share = ui.el('button', 'btn btn-ghost btn-sm', '生成分享文案');
            share.type = 'button';
            share.addEventListener('click', function () {
                generateShareCopy(itinerary, share);
            });
            actions.appendChild(share);

            var remove = ui.el('button', 'btn btn-ghost btn-sm', '删除');
            remove.type = 'button';
            remove.addEventListener('click', function () {
                removeItinerary(itinerary.id, remove, reload);
            });
            actions.appendChild(remove);

            head.appendChild(actions);
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
                    var label = item.name ? item.name : ('景点 #' + item.attraction_id);
                    tags.appendChild(ui.el('span', 'tag', label));
                });
                card.appendChild(tags);
            } else {
                card.appendChild(ui.el(
                    'p',
                    'itinerary-notes',
                    '还没有添加景点，可以在景点详情页点击「加入行程」。'
                ));
            }

            container.appendChild(card);
        });
    }

    function createItinerary(form, reload) {
        var errorNode = form.querySelector('[data-itinerary-error]');
        var submit = form.querySelector('button[type="submit"]');
        var title = (form.querySelector('[name="title"]').value || '').trim();
        var startDate = form.querySelector('[name="start_date"]').value || '';
        var endDate = form.querySelector('[name="end_date"]').value || '';
        var notes = (form.querySelector('[name="notes"]').value || '').trim();

        if (errorNode) {
            errorNode.textContent = '';
        }
        if (!title) {
            if (errorNode) {
                errorNode.textContent = '请填写行程名称';
            }
            return;
        }
        if (startDate && endDate && endDate < startDate) {
            if (errorNode) {
                errorNode.textContent = '结束日期不能早于开始日期';
            }
            return;
        }

        var payload = { title: title, attractions: [] };
        if (startDate) {
            payload.start_date = startDate;
        }
        if (endDate) {
            payload.end_date = endDate;
        }
        if (notes) {
            payload.notes = notes;
        }

        ui.setBusy(submit, true, '创建中…');
        api.post('/api/itineraries', payload).then(function () {
            ui.setBusy(submit, false);
            form.reset();
            ui.toast('行程创建成功', 'success');
            reload();
        }).catch(function (error) {
            ui.setBusy(submit, false);
            if (errorNode) {
                errorNode.textContent = error.message || '创建失败，请稍后重试';
            }
        });
    }

    function load() {
        var container = document.querySelector('[data-itinerary-list]');
        var form = document.querySelector('[data-itinerary-form]');
        if (!container) {
            return;
        }

        function reload() {
            ui.showSkeletons(container, 2);
            api.get('/api/itineraries').then(function (payload) {
                renderList(container, ui.extractList(payload).items, reload);
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

        if (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                createItinerary(form, reload);
            });
        }

        reload();
    }

    document.addEventListener('DOMContentLoaded', load);
})(window, document);
