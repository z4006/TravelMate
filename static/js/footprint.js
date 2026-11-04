/* TravelMate 旅行足迹页（任务 C）：SVG 足迹地图 + Canvas 打卡海报 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    /* 简化版中国轮廓（经纬度近似值，仅用于视觉呈现） */
    var CHINA_MAIN = [
        [73.5, 39.4], [75.0, 40.5], [76.5, 41.0], [80.2, 42.2], [80.3, 45.0],
        [82.5, 45.2], [83.0, 47.0], [85.0, 47.0], [87.0, 49.0], [90.0, 47.7],
        [95.0, 44.0], [96.5, 42.8], [100.0, 42.6], [105.0, 41.8], [110.0, 42.5],
        [111.5, 43.5], [115.0, 45.5], [117.5, 46.5], [119.5, 47.0], [117.8, 49.5],
        [120.0, 50.3], [121.5, 53.3], [125.0, 53.2], [127.0, 50.2], [130.7, 48.9],
        [134.5, 48.4], [135.0, 45.0], [131.0, 45.0], [130.6, 42.8], [128.0, 42.0],
        [125.5, 40.8], [124.4, 40.0], [121.5, 39.0], [122.0, 37.4], [119.0, 37.2],
        [120.8, 34.5], [121.9, 31.7], [121.0, 30.0], [122.5, 28.5], [120.0, 26.5],
        [117.5, 24.0], [114.0, 22.5], [110.5, 21.4], [109.5, 20.3], [108.0, 21.5],
        [106.0, 22.5], [105.0, 23.0], [102.0, 22.5], [99.0, 22.0], [97.5, 24.0],
        [98.0, 27.5], [96.0, 28.5], [92.0, 27.8], [88.8, 27.2], [85.8, 28.2],
        [81.0, 30.4], [78.7, 32.5], [76.0, 35.5], [74.5, 37.0]
    ];

    var CHINA_ISLANDS = [
        [[120.1, 25.3], [121.9, 25.2], [121.6, 22.9], [120.2, 22.6]],
        [[109.2, 20.1], [110.6, 20.1], [111.0, 19.6], [110.0, 18.2], [109.0, 18.4]]
    ];

    var LON_MIN = 72;
    var LON_MAX = 136;
    var LAT_MIN = 17;
    var LAT_MAX = 54.5;

    var SVG_W = 760;
    var SVG_H = 600;
    var SVG_PAD = 26;

    var state = {
        data: null,
        posterUrl: ''
    };

    var SVG_NS = 'http://www.w3.org/2000/svg';

    function svgEl(tag, attrs) {
        var node = document.createElementNS(SVG_NS, tag);
        if (attrs) {
            Object.keys(attrs).forEach(function (key) {
                node.setAttribute(key, attrs[key]);
            });
        }
        return node;
    }

    function project(lon, lat, width, height, pad) {
        var innerW = width - pad * 2;
        var innerH = height - pad * 2;
        var x = pad + (lon - LON_MIN) / (LON_MAX - LON_MIN) * innerW;
        var y = pad + (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * innerH;
        return [x, y];
    }

    function pathPoints(points, width, height, pad) {
        return points.map(function (point) {
            var xy = project(point[0], point[1], width, height, pad);
            return xy[0].toFixed(1) + ',' + xy[1].toFixed(1);
        }).join(' ');
    }

    /* ---------------- 统计卡片 ---------------- */

    function renderStats(container, data) {
        ui.clear(container);
        var stats = data.stats || {};
        var items = [
            ['已点亮城市', stats.city_count || 0, '座'],
            ['收藏景点', stats.favorite_count || 0, '个'],
            ['规划行程', stats.itinerary_count || 0, '条'],
            ['全国覆盖', stats.coverage || 0, '%']
        ];
        items.forEach(function (item) {
            var card = ui.el('div', 'fp-stat');
            card.appendChild(ui.el('span', 'fp-stat-value', item[1] + item[2]));
            card.appendChild(ui.el('span', 'fp-stat-label', item[0]));
            container.appendChild(card);
        });
    }

    /* ---------------- 等级卡 ---------------- */

    function renderLevel(container, data) {
        ui.clear(container);
        var level = data.level || {};
        var stats = data.stats || {};
        container.appendChild(ui.el('p', 'fp-level-title', '旅行等级 · ' + (level.title || '宅家观望')));

        var desc = '已点亮 ' + (level.cities || 0) + ' 座城市';
        if (level.next_threshold) {
            desc += '，再点亮 ' + (level.next_threshold - (level.cities || 0)) + ' 座升级';
        } else {
            desc += '，已达成最高等级';
        }
        container.appendChild(ui.el('p', 'fp-level-desc', desc));

        var bar = ui.el('div', 'fp-progress');
        var fill = ui.el('div', 'fp-progress-bar');
        var percent = level.next_threshold ? Math.round((level.progress || 0) * 100) : 100;
        fill.style.width = Math.max(4, Math.min(100, percent)) + '%';
        bar.appendChild(fill);
        container.appendChild(bar);

        if (stats.total_cities) {
            container.appendChild(ui.el(
                'p',
                'fp-level-desc',
                'TravelMate 已收录 ' + stats.total_cities + ' 个城市，等你继续点亮'
            ));
        }
    }

    /* ---------------- 城市列表 ---------------- */

    function renderCities(container, data) {
        ui.clear(container);
        var cities = data.cities || [];
        if (!cities.length) {
            container.appendChild(ui.el(
                'p',
                'fp-empty',
                '还没有点亮任何城市。先去「景点」页收藏几处喜欢的地方吧。'
            ));
            return;
        }
        cities.forEach(function (city) {
            var chip = ui.el('span', 'fp-city-chip', city.name);
            var count = (city.favorite_count || 0) + (city.itinerary_count || 0);
            chip.appendChild(ui.el('small', '', count + ' 处'));
            container.appendChild(chip);
        });
    }

    /* ---------------- SVG 地图 ---------------- */

    function renderMap(container, data) {
        ui.clear(container);

        var svg = svgEl('svg', {
            viewBox: '0 0 ' + SVG_W + ' ' + SVG_H,
            role: 'img',
            'aria-label': '中国旅行足迹地图'
        });

        var defs = svgEl('defs');
        var gradient = svgEl('linearGradient', { id: 'fp-land', x1: '0', y1: '0', x2: '0', y2: '1' });
        gradient.appendChild(svgEl('stop', { offset: '0%', 'stop-color': '#dff3ef' }));
        gradient.appendChild(svgEl('stop', { offset: '100%', 'stop-color': '#c7e7e3' }));
        defs.appendChild(gradient);
        svg.appendChild(defs);

        var shapes = [CHINA_MAIN].concat(CHINA_ISLANDS);
        shapes.forEach(function (shape) {
            svg.appendChild(svgEl('polygon', {
                points: pathPoints(shape, SVG_W, SVG_H, SVG_PAD),
                fill: 'url(#fp-land)',
                stroke: '#93c9c3',
                'stroke-width': '1.6',
                'stroke-linejoin': 'round'
            }));
        });

        var visited = {};
        (data.cities || []).forEach(function (city) {
            if (typeof city.lon === 'number' && typeof city.lat === 'number') {
                visited[city.name] = city;
            }
        });

        (data.background || []).forEach(function (city) {
            if (typeof city.lon !== 'number' || typeof city.lat !== 'number') {
                return;
            }
            if (visited[city.name]) {
                return;
            }
            var xy = project(city.lon, city.lat, SVG_W, SVG_H, SVG_PAD);
            svg.appendChild(svgEl('circle', {
                cx: xy[0].toFixed(1),
                cy: xy[1].toFixed(1),
                r: 2.4,
                class: 'fp-node fp-node-idle'
            }));
        });

        var ordered = Object.keys(visited).map(function (key) {
            return visited[key];
        }).sort(function (a, b) {
            return (b.favorite_count + b.itinerary_count) - (a.favorite_count + a.itinerary_count);
        });

        ordered.forEach(function (city, index) {
            var xy = project(city.lon, city.lat, SVG_W, SVG_H, SVG_PAD);
            var count = (city.favorite_count || 0) + (city.itinerary_count || 0);
            var radius = 5 + Math.min(6, count * 1.6);

            var dot = svgEl('circle', {
                cx: xy[0].toFixed(1),
                cy: xy[1].toFixed(1),
                r: radius.toFixed(1),
                class: 'fp-node fp-node-visited'
            });
            var tip = svgEl('title');
            tip.textContent = city.name + ' · ' + count + ' 处足迹';
            dot.appendChild(tip);
            svg.appendChild(dot);

            if (index < 14) {
                var label = svgEl('text', {
                    x: (xy[0] + radius + 3).toFixed(1),
                    y: (xy[1] + 4).toFixed(1),
                    class: 'fp-node-label'
                });
                label.textContent = city.name;
                svg.appendChild(label);
            }
        });

        container.appendChild(svg);

        if (!ordered.length) {
            container.appendChild(ui.el(
                'p',
                'fp-empty',
                '地图还没有亮点。收藏景点或创建行程后，这里会自动点亮。'
            ));
        }
    }

    /* ---------------- Canvas 海报 ---------------- */

    function roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }

    function drawPoster(data) {
        var canvas = document.createElement('canvas');
        canvas.width = 1080;
        canvas.height = 1440;
        var ctx = canvas.getContext('2d');
        var fontStack = '"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif';
        var stats = data.stats || {};
        var level = data.level || {};
        var cities = data.cities || [];

        var bg = ctx.createLinearGradient(0, 0, 1080, 1440);
        bg.addColorStop(0, '#0d4f49');
        bg.addColorStop(0.55, '#0b3b38');
        bg.addColorStop(1, '#072725');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, 1080, 1440);

        ctx.globalAlpha = 0.14;
        ctx.fillStyle = '#f59e0b';
        ctx.beginPath();
        ctx.arc(960, 150, 220, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(90, 1330, 200, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;

        ctx.fillStyle = 'rgba(255,255,255,.55)';
        ctx.font = '600 24px ' + fontStack;
        ctx.fillText('T R A V E L M A T E', 80, 120);

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 78px ' + fontStack;
        ctx.fillText('我的旅行足迹', 80, 216);

        ctx.fillStyle = '#fbbf24';
        ctx.font = '600 30px ' + fontStack;
        ctx.fillText('旅行等级 · ' + (level.title || '宅家观望'), 82, 274);

        ctx.fillStyle = 'rgba(255,255,255,.55)';
        ctx.font = '24px ' + fontStack;
        ctx.fillText('已点亮 ' + (stats.city_count || 0) + ' 座城市 · 覆盖全国 ' +
            (stats.coverage || 0) + '%', 82, 316);

        /* 地图卡片 */
        var mapX = 80;
        var mapY = 360;
        var mapW = 920;
        var mapH = 560;

        ctx.fillStyle = 'rgba(255,255,255,.07)';
        roundRect(ctx, mapX, mapY, mapW, mapH, 32);
        ctx.fill();

        var pad = 46;
        var innerW = mapW - pad * 2;
        var innerH = mapH - pad * 2;

        function posterPoint(lon, lat) {
            return [
                mapX + pad + (lon - LON_MIN) / (LON_MAX - LON_MIN) * innerW,
                mapY + pad + (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * innerH
            ];
        }

        var shapes = [CHINA_MAIN].concat(CHINA_ISLANDS);
        shapes.forEach(function (shape) {
            ctx.beginPath();
            shape.forEach(function (point, index) {
                var xy = posterPoint(point[0], point[1]);
                if (index === 0) {
                    ctx.moveTo(xy[0], xy[1]);
                } else {
                    ctx.lineTo(xy[0], xy[1]);
                }
            });
            ctx.closePath();
            ctx.fillStyle = 'rgba(204,251,241,.16)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(204,251,241,.55)';
            ctx.lineWidth = 2;
            ctx.stroke();
        });

        (data.background || []).forEach(function (city) {
            if (typeof city.lon !== 'number' || typeof city.lat !== 'number') {
                return;
            }
            if (city.visited) {
                return;
            }
            var xy = posterPoint(city.lon, city.lat);
            ctx.beginPath();
            ctx.arc(xy[0], xy[1], 2.6, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,255,255,.28)';
            ctx.fill();
        });

        cities.forEach(function (city, index) {
            if (typeof city.lon !== 'number' || typeof city.lat !== 'number') {
                return;
            }
            var xy = posterPoint(city.lon, city.lat);
            var count = (city.favorite_count || 0) + (city.itinerary_count || 0);
            var radius = 8 + Math.min(10, count * 2);

            ctx.beginPath();
            ctx.arc(xy[0], xy[1], radius + 10, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(245,158,11,.22)';
            ctx.fill();

            ctx.beginPath();
            ctx.arc(xy[0], xy[1], radius, 0, Math.PI * 2);
            ctx.fillStyle = '#fbbf24';
            ctx.fill();
            ctx.strokeStyle = 'rgba(255,255,255,.9)';
            ctx.lineWidth = 2.5;
            ctx.stroke();

            if (index < 10) {
                ctx.fillStyle = '#ffffff';
                ctx.font = '600 22px ' + fontStack;
                ctx.fillText(city.name, xy[0] + radius + 6, xy[1] + 8);
            }
        });

        /* 统计四条 */
        var statTop = 966;
        var statItems = [
            ['城市', stats.city_count || 0],
            ['收藏', stats.favorite_count || 0],
            ['行程', stats.itinerary_count || 0],
            ['覆盖', (stats.coverage || 0) + '%']
        ];
        statItems.forEach(function (item, index) {
            var boxX = 80 + index * 232;
            ctx.fillStyle = 'rgba(255,255,255,.08)';
            roundRect(ctx, boxX, statTop, 208, 132, 22);
            ctx.fill();

            ctx.fillStyle = '#fbbf24';
            ctx.font = 'bold 46px ' + fontStack;
            ctx.textAlign = 'center';
            ctx.fillText(String(item[1]), boxX + 104, statTop + 66);

            ctx.fillStyle = 'rgba(255,255,255,.72)';
            ctx.font = '22px ' + fontStack;
            ctx.fillText(item[0], boxX + 104, statTop + 104);
            ctx.textAlign = 'left';
        });

        /* 城市清单 */
        var listY = 1148;
        ctx.fillStyle = 'rgba(255,255,255,.65)';
        ctx.font = '600 26px ' + fontStack;
        ctx.fillText('点亮的城市', 80, listY);

        var names = cities.map(function (city) {
            return city.name;
        });
        if (!names.length) {
            names = ['还没有点亮的城市，去收藏心动的景点吧'];
        }

        ctx.font = '28px ' + fontStack;
        ctx.fillStyle = '#ffffff';
        var lineText = '';
        var cursorY = listY + 56;
        var maxWidth = 920;
        names.forEach(function (name) {
            var piece = lineText ? ' · ' + name : name;
            if (ctx.measureText(lineText + piece).width > maxWidth && lineText) {
                ctx.fillText(lineText, 80, cursorY);
                cursorY += 44;
                lineText = name;
            } else {
                lineText += piece;
            }
        });
        if (lineText) {
            ctx.fillText(lineText, 80, cursorY);
        }

        /* 页脚 */
        ctx.strokeStyle = 'rgba(255,255,255,.18)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(80, 1330);
        ctx.lineTo(1000, 1330);
        ctx.stroke();

        ctx.fillStyle = 'rgba(255,255,255,.6)';
        ctx.font = '24px ' + fontStack;
        ctx.fillText('TravelMate · 旅游信息与行程规划', 80, 1382);

        ctx.textAlign = 'right';
        ctx.fillStyle = 'rgba(251,191,36,.9)';
        ctx.font = '600 24px ' + fontStack;
        ctx.fillText('travelmate.fun', 1000, 1382);
        ctx.textAlign = 'left';

        return canvas.toDataURL('image/png');
    }

    function showPoster(data) {
        var panel = document.querySelector('[data-fp-posters]');
        var img = document.querySelector('[data-fp-poster-img]');
        var link = document.querySelector('[data-fp-download]');
        if (!panel || !img) {
            return;
        }
        state.posterUrl = drawPoster(data);
        img.src = state.posterUrl;
        if (link) {
            link.href = state.posterUrl;
            link.setAttribute(
                'download',
                'travelmate-footprint-' + new Date().toISOString().slice(0, 10) + '.png'
            );
        }
        panel.hidden = false;
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function showLoginRequired(container) {
        ui.clear(container);
        container.appendChild(ui.buildState(
            '请先登录',
            '登录后才能查看自己的旅行足迹地图。',
            '去登录',
            function () {
                window.location.assign(document.body.getAttribute('data-login-url') || '/login');
            }
        ));
    }

    function render(data) {
        state.data = data;
        var statsBox = document.querySelector('[data-fp-stats]');
        var mapBox = document.querySelector('[data-fp-map]');
        var levelBox = document.querySelector('[data-fp-level]');
        var cityBox = document.querySelector('[data-fp-cities]');

        if (statsBox) {
            renderStats(statsBox, data);
        }
        if (mapBox) {
            renderMap(mapBox, data);
        }
        if (levelBox) {
            renderLevel(levelBox, data);
        }
        if (cityBox) {
            renderCities(cityBox, data);
        }
    }

    function load() {
        var shell = document.querySelector('[data-footprint]');
        if (!shell) {
            return;
        }
        var mapBox = document.querySelector('[data-fp-map]');
        if (mapBox) {
            ui.showSkeletons(mapBox, 1);
        }

        api.get('/api/footprint').then(function (payload) {
            // TMApi 已自动解包 {success, message, data}，这里 payload 就是 data 本体
            render(payload || {});
        }).catch(function (error) {
            if (error.status === 401) {
                showLoginRequired(mapBox || shell);
                return;
            }
            if (mapBox) {
                ui.clear(mapBox);
                mapBox.appendChild(ui.buildState(
                    '暂时无法加载足迹',
                    error.message || '请稍后重试。',
                    '重新加载',
                    load
                ));
            }
        });
    }

    function bindPosterButton() {
        var button = document.querySelector('[data-fp-poster]');
        var panel = document.querySelector('[data-fp-posters]');
        var closeBtn = document.querySelector('[data-fp-close-poster]');

        if (button) {
            button.addEventListener('click', function () {
                if (!state.data) {
                    ui.toast('足迹数据还在加载中，请稍候', 'error');
                    return;
                }
                ui.setBusy(button, true, '生成中…');
                window.setTimeout(function () {
                    try {
                        showPoster(state.data);
                        ui.toast('足迹海报已生成', 'success');
                    } catch (error) {
                        ui.toast('海报生成失败，请重试', 'error');
                    }
                    ui.setBusy(button, false);
                }, 30);
            });
        }

        if (closeBtn && panel) {
            closeBtn.addEventListener('click', function () {
                panel.hidden = true;
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        bindPosterButton();
        load();
    });
})(window, document);
