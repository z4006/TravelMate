/* TravelMate 首页：加载热门景点 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function loadPopularAttractions() {
        var grid = document.querySelector('[data-attraction-grid]');
        if (!grid) {
            return;
        }
        var limit = parseInt(grid.getAttribute('data-limit'), 10) || 6;
        ui.showSkeletons(grid, limit);

        api.get('/api/attractions', { page_size: 100 }).then(function (payload) {
            var result = ui.extractList(payload);
            var items = result.items;

            // 首页优先展示图片已本地化的景点，保证每张卡片都能出图；
            // 本地图不够时用其余景点补齐。
            var localImage = items.filter(function (item) {
                var url = item && item.image_url;
                return typeof url === 'string' && url.indexOf('/static/') === 0;
            });
            // 同一张风景图可能被多个景点复用，首页按图片去重，避免视觉重复
            var seen = {};
            var distinct = localImage.filter(function (item) {
                var url = item.image_url;
                if (seen[url]) {
                    return false;
                }
                seen[url] = true;
                return true;
            });
            var chosen = distinct.length >= limit
                ? distinct
                : (localImage.length >= limit ? localImage : items);

            ui.renderCards(grid, chosen, {
                limit: limit,
                emptyTitle: '景点数据还在准备中',
                emptyDesc: '景点数据暂时没有返回内容，稍后再来看看。'
            });
        }).catch(function (error) {
            ui.clear(grid);
            grid.appendChild(ui.buildState(
                '暂时无法加载景点',
                error.status === 404
                    ? '景点数据接口暂未开放，请稍后再试。'
                    : (error.message || '请稍后重试。'),
                '重新加载',
                loadPopularAttractions
            ));
        });
    }

    document.addEventListener('DOMContentLoaded', loadPopularAttractions);
})(window, document);
