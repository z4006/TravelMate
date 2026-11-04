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
