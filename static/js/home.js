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

        api.get('/api/attractions').then(function (payload) {
            var result = ui.extractList(payload);
            ui.renderCards(grid, result.items, {
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
