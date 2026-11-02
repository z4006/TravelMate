/* TravelMate 景点列表页：按城市 / 关键词查询，支持服务端与本地双重筛选 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function currentQuery() {
        var params = new URLSearchParams(window.location.search);
        return {
            city: (params.get('city') || '').trim(),
            keyword: (params.get('keyword') || '').trim()
        };
    }

    function fillControls(criteria) {
        var cityInput = document.querySelector('[data-filter-city]') || document.getElementById('filter-city');
        var keywordInput = document.querySelector('[data-filter-keyword]') || document.getElementById('filter-keyword');
        if (cityInput) {
            cityInput.value = criteria.city;
        }
        if (keywordInput) {
            keywordInput.value = criteria.keyword;
        }
    }

    function describeFilter(criteria) {
        var parts = [];
        if (criteria.city) {
            parts.push('城市：' + criteria.city);
        }
        if (criteria.keyword) {
            parts.push('关键词：' + criteria.keyword);
        }
        return parts.length ? parts.join('　·　') : '';
    }

    // 后端若未实现关键词过滤，前端再按名称/简介过滤一次，保证搜索结果可用
    function matchKeyword(item, keyword) {
        if (!keyword) {
            return true;
        }
        var text = (item.name + ' ' + item.summary + ' ' + item.city + ' ' + item.tags.join(' ')).toLowerCase();
        return text.indexOf(keyword.toLowerCase()) !== -1;
    }

    function load(criteria, grid, countNode, filterNode) {
        ui.showSkeletons(grid, 6);
        if (countNode) {
            countNode.textContent = '正在加载景点…';
        }

        var serverQuery = {};
        if (criteria.city) {
            serverQuery.city = criteria.city;
        }
        if (criteria.keyword) {
            serverQuery.q = criteria.keyword;
        }

        api.get('/api/attractions', serverQuery).then(function (payload) {
            var result = ui.extractList(payload);
            var items = result.items.filter(function (raw) {
                var item = ui.normalizeAttraction(raw);
                if (!item) {
                    return false;
                }
                if (criteria.city && item.city && item.city.indexOf(criteria.city) === -1) {
                    return false;
                }
                return matchKeyword(item, criteria.keyword);
            });

            var rendered = ui.renderCards(grid, items, {
                emptyTitle: '没有找到匹配的景点',
                emptyDesc: criteria.city || criteria.keyword
                    ? '试着放宽筛选条件，或查看全部景点。'
                    : '景点接口暂时没有返回数据，稍后再来看看。',
                emptyActionLabel: (criteria.city || criteria.keyword) ? '查看全部景点' : '',
                emptyAction: function () {
                    window.location.assign(window.location.pathname);
                }
            });

            if (countNode) {
                ui.clear(countNode);
                countNode.appendChild(document.createTextNode('共找到 '));
                countNode.appendChild(ui.el('strong', null, String(rendered.length)));
                countNode.appendChild(document.createTextNode(' 个景点'));
            }
            if (filterNode) {
                filterNode.textContent = describeFilter(criteria);
            }
        }).catch(function (error) {
            ui.clear(grid);
            grid.appendChild(ui.buildState(
                '暂时无法加载景点',
                error.status === 404
                    ? '景点数据接口暂未开放，请稍后再试。'
                    : (error.message || '请稍后重试。'),
                '重新加载',
                function () {
                    load(criteria, grid, countNode, filterNode);
                }
            ));
            if (countNode) {
                countNode.textContent = '';
            }
            if (filterNode) {
                filterNode.textContent = describeFilter(criteria);
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var grid = document.querySelector('[data-attraction-grid]');
        if (!grid) {
            return;
        }
        var criteria = currentQuery();
        var countNode = document.querySelector('[data-result-count]');
        var filterNode = document.querySelector('[data-active-filter]');
        fillControls(criteria);
        load(criteria, grid, countNode, filterNode);
    });
})(window, document);
