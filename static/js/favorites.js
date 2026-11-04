/* TravelMate 我的收藏页（成员 D 接入） */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function priceText(raw) {
        if (typeof raw.ticket_price_cents !== 'number') {
            return '';
        }
        if (raw.ticket_price_cents === 0) {
            return '免费';
        }
        return '¥' + (raw.ticket_price_cents / 100).toFixed(0);
    }

    function toItem(raw) {
        var item = ui.normalizeAttraction(raw);
        if (!item) {
            return null;
        }
        // 收藏接口返回 {id: 收藏记录ID, attraction_id: 景点ID}，
        // 卡片链接与取消收藏都必须使用 attraction_id，否则会操作到错误的记录。
        if (raw.attraction_id !== undefined && raw.attraction_id !== null) {
            item.id = raw.attraction_id;
        }
        var price = priceText(raw);
        if (price) {
            item.priceText = price;
        }
        return item;
    }

    function showLoginRequired(grid, countNode) {
        ui.clear(grid);
        grid.appendChild(ui.buildState(
            '请先登录',
            '登录后即可查看你收藏的景点。',
            '去登录',
            function () {
                window.location.assign(document.body.getAttribute('data-login-url') || '/login');
            }
        ));
        if (countNode) {
            countNode.textContent = '';
        }
    }

    function removeFavorite(attractionId, button, reload) {
        ui.setBusy(button, true, '取消中…');
        api.request('/api/favorites/' + encodeURIComponent(attractionId), { method: 'DELETE' })
            .then(function () {
                ui.toast('已取消收藏', 'success');
                reload();
            })
            .catch(function (error) {
                ui.setBusy(button, false);
                ui.toast(error.message || '取消收藏失败', 'error');
            });
    }

    function render(grid, items, reload) {
        ui.clear(grid);
        items.forEach(function (item) {
            var card = ui.createAttractionCard(item);
            var foot = card.querySelector('.attraction-foot');
            if (foot) {
                var button = ui.el('button', 'btn btn-ghost btn-sm', '取消收藏');
                button.type = 'button';
                button.addEventListener('click', function () {
                    removeFavorite(item.id, button, reload);
                });
                foot.appendChild(button);
            }
            grid.appendChild(card);
        });
    }

    function load() {
        var grid = document.querySelector('[data-favorite-grid]');
        if (!grid) {
            return;
        }
        var countNode = document.querySelector('[data-favorite-count]');
        ui.showSkeletons(grid, 4);
        if (countNode) {
            countNode.textContent = '正在加载收藏…';
        }
        api.get('/api/favorites').then(function (payload) {
            var list = ui.extractList(payload).items;
            var items = list.map(toItem).filter(Boolean);
            if (countNode) {
                countNode.textContent = '共收藏 ' + items.length + ' 个景点';
            }
            if (!items.length) {
                ui.clear(grid);
                grid.appendChild(ui.buildState(
                    '还没有收藏任何景点',
                    '在景点详情页点击「收藏」，就会出现在这里。',
                    '去看看景点',
                    function () {
                        window.location.assign('/attractions');
                    }
                ));
                return;
            }
            render(grid, items, load);
        }).catch(function (error) {
            if (error.status === 401) {
                showLoginRequired(grid, countNode);
                return;
            }
            ui.clear(grid);
            grid.appendChild(ui.buildState(
                '暂时无法加载收藏',
                error.message || '请稍后重试。',
                '重新加载',
                load
            ));
            if (countNode) {
                countNode.textContent = '';
            }
        });
    }

    document.addEventListener('DOMContentLoaded', load);
})(window, document);
