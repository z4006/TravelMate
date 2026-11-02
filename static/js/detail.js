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


/* 收藏与加入行程（成员 D 接入） */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function applyFavoriteState(button, favorited) {
        button.textContent = favorited ? '已收藏（点击取消）' : '收藏';
        button.setAttribute('data-favorited', favorited ? 'true' : 'false');
        button.classList.toggle('btn-primary', !favorited);
        button.classList.toggle('btn-ghost', favorited);
    }

    function findFavoriteId(list, attractionId) {
        for (var i = 0; i < list.length; i += 1) {
            var row = list[i] || {};
            var id = row.attraction_id !== undefined ? row.attraction_id : row.id;
            if (Number(id) === attractionId) {
                return id;
            }
        }
        return null;
    }

    function setup(root, attractionId) {
        var button = root.querySelector('[data-favorite-toggle]');
        var adder = root.querySelector('[data-itinerary-adder]');
        var select = root.querySelector('[data-itinerary-select]');
        var addButton = root.querySelector('[data-itinerary-add]');
        if (!button) {
            return;
        }

        function loadFavorites() {
            api.get('/api/favorites').then(function (payload) {
                var list = ui.extractList(payload).items;
                applyFavoriteState(button, findFavoriteId(list, attractionId) !== null);
            }).catch(function () {
                applyFavoriteState(button, false);
            });
        }

        function addToItinerary(itineraryId) {
            if (!itineraryId || !addButton) {
                return;
            }
            ui.setBusy(addButton, true, '添加中…');
            api.get('/api/itineraries/' + encodeURIComponent(itineraryId)).then(function (itinerary) {
                var attractions = (itinerary.attractions || []).map(function (item) {
                    var payload = { attraction_id: item.attraction_id };
                    if (item.visit_date) {
                        payload.visit_date = item.visit_date;
                    }
                    if (typeof item.sort_order === 'number') {
                        payload.sort_order = item.sort_order;
                    }
                    if (item.notes) {
                        payload.notes = item.notes;
                    }
                    return payload;
                });
                var exists = attractions.some(function (item) {
                    return Number(item.attraction_id) === attractionId;
                });
                if (exists) {
                    ui.setBusy(addButton, false);
                    ui.toast('这个景点已经在该行程里了', 'info');
                    return null;
                }
                attractions.push({ attraction_id: attractionId });
                return api.put('/api/itineraries/' + encodeURIComponent(itineraryId), {
                    title: itinerary.title,
                    start_date: itinerary.start_date || null,
                    end_date: itinerary.end_date || null,
                    notes: itinerary.notes || null,
                    attractions: attractions
                });
            }).then(function (result) {
                if (result === null) {
                    return;
                }
                ui.setBusy(addButton, false);
                ui.toast('已加入行程', 'success');
            }).catch(function (error) {
                ui.setBusy(addButton, false);
                ui.toast(error.message || '加入行程失败', 'error');
            });
        }

        function loadItineraries() {
            if (!adder || !select) {
                return;
            }
            api.get('/api/itineraries').then(function (payload) {
                var items = ui.extractList(payload).items;
                if (!items.length) {
                    adder.hidden = true;
                    return;
                }
                ui.clear(select);
                items.forEach(function (itinerary) {
                    var option = document.createElement('option');
                    option.value = String(itinerary.id);
                    option.textContent = itinerary.title || ('行程 #' + itinerary.id);
                    select.appendChild(option);
                });
                adder.hidden = false;
                if (addButton) {
                    addButton.addEventListener('click', function () {
                        addToItinerary(Number(select.value));
                    });
                }
            }).catch(function () {
                adder.hidden = true;
            });
        }

        api.get('/api/user/info').then(function (profile) {
            if (!profile) {
                return;
            }
            button.hidden = false;
            loadFavorites();
            loadItineraries();

            button.addEventListener('click', function () {
                var favorited = button.getAttribute('data-favorited') === 'true';
                ui.setBusy(button, true, favorited ? '取消中…' : '收藏中…');
                var request = favorited
                    ? api.request('/api/favorites/' + encodeURIComponent(attractionId), { method: 'DELETE' })
                    : api.post('/api/favorites', { attraction_id: attractionId });
                request.then(function () {
                    ui.setBusy(button, false);
                    applyFavoriteState(button, !favorited);
                    ui.toast(favorited ? '已取消收藏' : '收藏成功', 'success');
                }).catch(function (error) {
                    ui.setBusy(button, false);
                    ui.toast(error.message || '操作失败', 'error');
                });
            });
        }).catch(function () {
            return;
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-attraction-id]');
        if (!root) {
            return;
        }
        var raw = (root.getAttribute('data-attraction-id') || '').trim();
        if (!/^[0-9]+$/.test(raw)) {
            return;
        }
        setup(root, parseInt(raw, 10));
    });
})(window, document);
