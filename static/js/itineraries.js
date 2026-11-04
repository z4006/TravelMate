/* TravelMate 已保存行程页（成员 D）：查看、生成文案、删除 */
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

    function toggleCaption(card, text) {
        var existing = card.querySelector('[data-caption-box]');
        if (existing) {
            existing.parentNode.removeChild(existing);
            return;
        }
        card.appendChild(buildCaptionBox(text));
    }

    function generateCaption(card, button, itinerary, reload) {
        ui.setBusy(button, true, '生成中…');
        api.post('/api/itineraries/' + encodeURIComponent(itinerary.id) + '/caption', {})
            .then(function (data) {
                ui.setBusy(button, false);
                ui.toast('文案已生成', 'success');
                var box = buildCaptionBox(data.caption || '');
                var old = card.querySelector('[data-caption-box]');
                if (old) {
                    old.parentNode.removeChild(old);
                }
                card.appendChild(box);
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

    function renderList(container, items, reload) {
        ui.clear(container);
        if (!items.length) {
            container.appendChild(ui.buildState(
                '还没有保存的行程',
                '去 AI 助手生成一份行程并保存，就会出现在这里。',
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
                    var label = item.name ? item.name : ('景点 #' + item.attraction_id);
                    tags.appendChild(ui.el('span', 'tag', label));
                });
                card.appendChild(tags);
            } else {
                card.appendChild(ui.el('p', 'itinerary-notes', '还没有添加景点'));
            }

            var actions = ui.el('div', 'plan-actions');

            if (itinerary.caption) {
                var viewBtn = ui.el('button', 'btn btn-ghost btn-sm', '查看我的文案');
                viewBtn.type = 'button';
                viewBtn.addEventListener('click', function () {
                    toggleCaption(card, itinerary.caption);
                });
                actions.appendChild(viewBtn);
            } else {
                var genBtn = ui.el('button', 'btn btn-primary btn-sm', '✍️ 生成分享文案');
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
