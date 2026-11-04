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
