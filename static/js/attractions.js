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

    // 后端 page_size 上限为 100，传更大值会直接返回 400；这里按上限分页取完
    var PAGE_SIZE = 100;
    var MAX_PAGES = 50;

    function fetchPage(criteria, page) {
        var query = { page: page, page_size: PAGE_SIZE };
        if (criteria.city) {
            query.city = criteria.city;
        }
        if (criteria.keyword) {
            query.q = criteria.keyword;
        }
        return api.get('/api/attractions', query).then(function (payload) {
            return ui.extractList(payload);
        });
    }

    function fetchAll(criteria) {
        var items = [];
        var total = 0;
        function step(page) {
            return fetchPage(criteria, page).then(function (result) {
                if (result.total) {
                    total = result.total;
                }
                items = items.concat(result.items);
                var more = result.items.length > 0
                    && items.length < total
                    && page < MAX_PAGES;
                return more ? step(page + 1) : { items: items, total: total };
            });
        }
        return step(1);
    }

    function load(criteria, grid, countNode, filterNode, summaryNode) {
        ui.showSkeletons(grid, 6);
        if (countNode) {
            countNode.textContent = '正在加载景点…';
        }

        fetchAll(criteria).then(function (result) {
            if (summaryNode) {
                summaryNode.textContent = criteria.city
                    ? '当前城市：' + criteria.city + '，共找到 ' + result.total + ' 个核心景点'
                    : '当前城市：全部城市，共找到 ' + result.total + ' 个核心景点';
            }
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
                countNode.appendChild(ui.el('strong', null, String(result.total)));
                countNode.appendChild(document.createTextNode(
                    rendered.length < result.total
                        ? ' 个景点（当前显示前 ' + rendered.length + ' 个）'
                        : ' 个景点'
                ));
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
                    load(criteria, grid, countNode, filterNode, summaryNode);
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
        var summaryNode = document.querySelector('[data-city-summary]');
        fillControls(criteria);
        load(criteria, grid, countNode, filterNode, summaryNode);
    });
})(window, document);
