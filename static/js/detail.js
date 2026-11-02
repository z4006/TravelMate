/* TravelMate 景点详情页：根据 URL 中的景点编号调用 /api/attractions/<id> */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function setText(root, selector, value, fallback) {
        var node = root.querySelector(selector);
        if (!node) {
            return;
        }
        node.textContent = value || fallback || '';
    }

    function renderAttraction(root, item) {
        document.title = item.name + ' - TravelMate';

        var image = root.querySelector('[data-detail-image]');
        if (image) {
            image.src = item.image || ui.placeholderImage();
            image.alt = item.name;
            image.addEventListener('error', function () {
                image.src = ui.placeholderImage();
                image.alt = '';
            }, { once: true });
        }

        var city = root.querySelector('[data-detail-city]');
        if (city) {
            city.textContent = item.city;
            city.hidden = !item.city;
        }

        setText(root, '[data-detail-name]', item.name);

        var rating = root.querySelector('[data-detail-rating]');
        if (rating) {
            rating.textContent = item.rating ? '评分 ' + item.rating : '';
            rating.hidden = !item.rating;
        }

        var tags = root.querySelector('[data-detail-tags]');
        if (tags) {
            ui.clear(tags);
            item.tags.forEach(function (tag) {
                tags.appendChild(ui.el('span', 'tag', tag));
            });
            tags.hidden = !item.tags.length;
        }

        setText(root, '[data-detail-description]', item.summary, '这个景点还没有详细介绍，信息稍后补充。');
        setText(root, '[data-detail-hours]', item.hours, '暂无信息');
        setText(root, '[data-detail-price]', item.priceText, '暂无信息');
        setText(root, '[data-detail-address]', item.address, '暂无信息');
        setText(root, '[data-detail-phone]', item.phone, '暂无信息');
    }

    function load(root, attractionId) {
        var loading = root.querySelector('[data-detail-loading]');
        var body = root.querySelector('[data-detail-body]');
        var errorBox = root.querySelector('[data-detail-error]');

        if (loading) {
            loading.hidden = false;
        }
        if (body) {
            body.hidden = true;
        }
        if (errorBox) {
            errorBox.hidden = true;
            ui.clear(errorBox);
        }

        api.get('/api/attractions/' + encodeURIComponent(attractionId)).then(function (payload) {
            var raw = (payload && typeof payload === 'object' && payload.attraction) ? payload.attraction : payload;
            var item = ui.normalizeAttraction(raw);
            if (!item) {
                throw new api.ApiError('景点数据格式不正确，请确认接口返回字段', 0, payload);
            }
            if (loading) {
                loading.hidden = true;
            }
            if (body) {
                body.hidden = false;
            }
            renderAttraction(root, item);
        }).catch(function (error) {
            if (loading) {
                loading.hidden = true;
            }
            if (body) {
                body.hidden = true;
            }
            if (!errorBox) {
                return;
            }
            errorBox.hidden = false;
            errorBox.appendChild(ui.buildState(
                error.status === 404 ? '找不到这个景点' : '暂时无法加载景点详情',
                error.status === 404
                    ? '景点接口返回 404：请检查地址栏中的景点编号，或确认景点接口是否已经上线。'
                    : (error.message || '请稍后重试。'),
                '重新加载',
                function () {
                    load(root, attractionId);
                }
            ));
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-attraction-id]');
        if (!root) {
            return;
        }
        var attractionId = (root.getAttribute('data-attraction-id') || '').trim();
        if (!/^\d+$/.test(attractionId)) {
            var errorBox = root.querySelector('[data-detail-error]');
            var loading = root.querySelector('[data-detail-loading]');
            if (loading) {
                loading.hidden = true;
            }
            if (errorBox) {
                errorBox.hidden = false;
                errorBox.appendChild(ui.buildState('景点编号不正确', '请返回景点列表重新选择。'));
            }
            return;
        }
        load(root, attractionId);
    });
})(window, document);
