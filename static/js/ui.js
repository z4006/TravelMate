/* TravelMate 通用界面工具：DOM 构建、提示条、表单错误、景点卡片渲染 */
(function (window, document) {
    'use strict';

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined && text !== null && text !== '') {
            node.textContent = String(text);
        }
        return node;
    }

    function clear(node) {
        if (!node) {
            return;
        }
        while (node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function pick(source, keys) {
        if (!source || typeof source !== 'object') {
            return null;
        }
        for (var i = 0; i < keys.length; i += 1) {
            var value = source[keys[i]];
            if (value !== undefined && value !== null && value !== '') {
                return value;
            }
        }
        return null;
    }

    function asText(value) {
        if (value === undefined || value === null) {
            return '';
        }
        if (typeof value === 'string') {
            return value.trim();
        }
        if (typeof value === 'number') {
            return String(value);
        }
        return '';
    }

    function toTags(value) {
        if (!value) {
            return [];
        }
        if (Array.isArray(value)) {
            return value.map(asText).filter(function (tag) {
                return tag !== '';
            }).slice(0, 4);
        }
        if (typeof value === 'string') {
            return value.split(/[,，、|/]+/).map(function (tag) {
                return tag.trim();
            }).filter(function (tag) {
                return tag !== '';
            }).slice(0, 4);
        }
        return [];
    }

    function placeholderImage() {
        return document.body.getAttribute('data-placeholder-image') || '/static/images/placeholder-attraction.svg';
    }

    function detailUrl(id) {
        var base = document.body.getAttribute('data-detail-base') || '/attractions/';
        return base + encodeURIComponent(String(id));
    }

    // 兼容景点接口可能使用的字段命名，统一成前端内部结构
    function normalizeAttraction(raw) {
        if (!raw || typeof raw !== 'object') {
            return null;
        }
        var id = pick(raw, ['id', 'attraction_id', 'attractionId', 'pk']);
        if (id === null) {
            return null;
        }
        var price = pick(raw, ['ticket_price', 'price', 'ticket', 'admission']);
        var rating = pick(raw, ['rating', 'score', 'rate']);
        return {
            id: id,
            name: asText(pick(raw, ['name', 'title', 'attraction_name'])) || '未命名景点',
            city: asText(pick(raw, ['city', 'city_name', 'location', 'province'])),
            summary: asText(pick(raw, ['description', 'summary', 'intro', 'detail', 'content'])),
            image: asText(pick(raw, ['image_url', 'cover_url', 'image', 'cover', 'thumbnail', 'photo'])),
            tags: toTags(pick(raw, ['tags', 'tag', 'labels', 'category'])),
            rating: rating === null ? '' : asText(rating),
            hours: asText(pick(raw, ['open_time', 'opening_hours', 'hours', 'business_hours'])),
            priceText: price === null ? '' : (typeof price === 'number' ? '¥' + price : asText(price)),
            address: asText(pick(raw, ['address', 'addr', 'location_address'])),
            phone: asText(pick(raw, ['phone', 'telephone', 'tel', 'contact']))
        };
    }

    // data 可能是数组，也可能是 {items,total} 之类的对象，两种都兼容
    function extractList(payload) {
        if (Array.isArray(payload)) {
            return { items: payload, total: payload.length };
        }
        if (!payload || typeof payload !== 'object') {
            return { items: [], total: 0 };
        }
        var keys = ['items', 'attractions', 'list', 'results', 'records', 'rows', 'data'];
        for (var i = 0; i < keys.length; i += 1) {
            var value = payload[keys[i]];
            if (Array.isArray(value)) {
                var total = pick(payload, ['total', 'count', 'total_count', 'totalCount']);
                return {
                    items: value,
                    total: typeof total === 'number' ? total : value.length
                };
            }
        }
        return { items: [], total: 0 };
    }

    function toast(message, type) {
        var region = document.getElementById('toast-region');
        if (!region || !message) {
            return;
        }
        var node = el('div', 'toast', message);
        node.setAttribute('data-type', type || 'info');
        region.appendChild(node);
        window.setTimeout(function () {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        }, 3600);
    }

    function setBusy(button, busy, busyLabel) {
        if (!button) {
            return;
        }
        if (busy) {
            if (!button.hasAttribute('data-idle-label')) {
                button.setAttribute('data-idle-label', button.textContent);
            }
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            if (busyLabel) {
                button.textContent = busyLabel;
            }
            return;
        }
        button.disabled = false;
        button.removeAttribute('aria-busy');
        if (button.hasAttribute('data-idle-label')) {
            button.textContent = button.getAttribute('data-idle-label');
            button.removeAttribute('data-idle-label');
        }
    }

    function showAlert(container, message, type) {
        if (!container) {
            return;
        }
        container.textContent = message || '';
        container.setAttribute('data-type', type || 'error');
        container.hidden = !message;
    }

    function hideAlert(container) {
        if (!container) {
            return;
        }
        container.textContent = '';
        container.hidden = true;
    }

    function setFieldError(form, name, message) {
        if (!form) {
            return;
        }
        var node = form.querySelector('[data-error-for="' + name + '"]');
        var input = form.querySelector('[name="' + name + '"]');
        if (node) {
            node.textContent = message || '';
        }
        if (input) {
            if (message) {
                input.setAttribute('aria-invalid', 'true');
            } else {
                input.removeAttribute('aria-invalid');
            }
        }
    }

    function clearFieldErrors(form) {
        if (!form) {
            return;
        }
        Array.prototype.forEach.call(form.querySelectorAll('[data-error-for]'), function (node) {
            node.textContent = '';
        });
        Array.prototype.forEach.call(form.querySelectorAll('[aria-invalid]'), function (input) {
            input.removeAttribute('aria-invalid');
        });
    }

    function buildState(title, description, actionLabel, onAction) {
        var block = el('div', 'state-block');
        block.appendChild(el('p', 'state-title', title));
        if (description) {
            block.appendChild(el('p', 'state-desc', description));
        }
        if (actionLabel) {
            var button = el('button', 'btn btn-ghost btn-sm', actionLabel);
            button.type = 'button';
            if (typeof onAction === 'function') {
                button.addEventListener('click', onAction);
            }
            block.appendChild(button);
        }
        return block;
    }

    function showSkeletons(container, count) {
        if (!container) {
            return;
        }
        clear(container);
        for (var i = 0; i < (count || 6); i += 1) {
            container.appendChild(el('div', 'skeleton skeleton-card'));
        }
    }

    function createAttractionCard(item) {
        var card = el('article', 'attraction-card');
        var media = el('div', 'attraction-media');
        var img = document.createElement('img');
        img.src = item.image || placeholderImage();
        img.alt = item.name;
        img.loading = 'lazy';
        img.width = 480;
        img.height = 300;
        img.addEventListener('error', function () {
            img.src = placeholderImage();
            img.alt = '';
        }, { once: true });
        media.appendChild(img);
        if (item.city) {
            media.appendChild(el('span', 'attraction-city', item.city));
        }

        var body = el('div', 'attraction-body');
        var heading = el('h3', 'attraction-name');
        var link = el('a', null, item.name);
        link.href = detailUrl(item.id);
        heading.appendChild(link);
        body.appendChild(heading);

        if (item.summary) {
            body.appendChild(el('p', 'attraction-summary', item.summary));
        }

        if (item.tags.length) {
            var tagList = el('div', 'tag-list');
            item.tags.forEach(function (tag) {
                tagList.appendChild(el('span', 'tag', tag));
            });
            body.appendChild(tagList);
        }

        var foot = el('div', 'attraction-foot');
        foot.appendChild(el('span', null, item.priceText || '门票信息待补充'));
        var more = el('a', 'attraction-link', '查看详情 →');
        more.href = link.href;
        foot.appendChild(more);
        body.appendChild(foot);

        card.appendChild(media);
        card.appendChild(body);
        return card;
    }

    function renderCards(container, rawItems, options) {
        if (!container) {
            return [];
        }
        var config = options || {};
        clear(container);
        var items = (rawItems || []).map(normalizeAttraction).filter(Boolean);
        if (config.limit > 0) {
            items = items.slice(0, config.limit);
        }
        if (!items.length) {
            container.appendChild(buildState(
                config.emptyTitle || '暂无景点数据',
                config.emptyDesc || '可以换一个城市或关键词再试试。',
                config.emptyActionLabel,
                config.emptyAction
            ));
            return items;
        }
        items.forEach(function (item) {
            container.appendChild(createAttractionCard(item));
        });
        return items;
    }

    window.TMUI = {
        el: el,
        clear: clear,
        pick: pick,
        asText: asText,
        toTags: toTags,
        placeholderImage: placeholderImage,
        detailUrl: detailUrl,
        normalizeAttraction: normalizeAttraction,
        extractList: extractList,
        toast: toast,
        setBusy: setBusy,
        showAlert: showAlert,
        hideAlert: hideAlert,
        setFieldError: setFieldError,
        clearFieldErrors: clearFieldErrors,
        buildState: buildState,
        showSkeletons: showSkeletons,
        createAttractionCard: createAttractionCard,
        renderCards: renderCards
    };
})(window, document);
