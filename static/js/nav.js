/* TravelMate 导航栏：登录态显示、退出登录、移动端菜单 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    function initNavToggle() {
        var toggle = document.querySelector('.nav-toggle');
        var nav = document.getElementById('site-nav');
        if (!toggle || !nav) {
            return;
        }
        toggle.addEventListener('click', function () {
            var opened = nav.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', opened ? 'true' : 'false');
        });
    }

    function markActive() {
        var current = document.body.getAttribute('data-page');
        if (!current) {
            return;
        }
        Array.prototype.forEach.call(document.querySelectorAll('.nav-link'), function (link) {
            if (link.getAttribute('data-nav') === current) {
                link.classList.add('is-active');
                link.setAttribute('aria-current', 'page');
            }
        });
    }

    function renderGuest() {
        var guest = document.querySelector('[data-nav-guest]');
        var user = document.querySelector('[data-nav-user]');
        if (guest) {
            guest.hidden = false;
        }
        if (user) {
            user.hidden = true;
        }
    }

    function renderUser(profile) {
        var guest = document.querySelector('[data-nav-guest]');
        var user = document.querySelector('[data-nav-user]');
        var nameNode = document.querySelector('[data-nav-username]');
        var avatar = document.querySelector('[data-nav-avatar]');
        if (!profile || !profile.username) {
            renderGuest();
            return;
        }
        var displayName = profile.nickname || profile.username;
        if (nameNode) {
            nameNode.textContent = displayName;
            nameNode.title = profile.username;
        }
        if (avatar) {
            avatar.textContent = displayName.charAt(0).toUpperCase();
        }
        if (guest) {
            guest.hidden = true;
        }
        if (user) {
            user.hidden = false;
        }
    }

    function loadCurrentUser() {
        // 登录态只能由服务端 /api/user/info 判定，前端不保存角色或用户编号
        return api.get('/api/user/info').then(function (profile) {
            renderUser(profile);
            return profile;
        }).catch(function () {
            renderGuest();
            return null;
        });
    }

    function initLogout() {
        var button = document.querySelector('[data-nav-logout]');
        if (!button) {
            return;
        }
        button.addEventListener('click', function () {
            ui.setBusy(button, true, '退出中…');
            api.post('/api/logout').then(function () {
                // 退出后 Session 已重建，必须重新获取 CSRF Token 再继续写操作
                return api.refreshCsrfToken().catch(function () {
                    return null;
                });
            }).then(function () {
                ui.toast('已退出登录', 'success');
                window.setTimeout(function () {
                    window.location.assign('/');
                }, 300);
            }).catch(function (error) {
                ui.setBusy(button, false);
                ui.toast(error.message || '退出登录失败', 'error');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initNavToggle();
        markActive();
        initLogout();
        loadCurrentUser();
    });
})(window, document);
