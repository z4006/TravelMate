/* TravelMate 登录 / 注册页面：前端校验 + 调用后端认证接口 + CSRF 处理 */
(function (window, document) {
    'use strict';

    var api = window.TMApi;
    var ui = window.TMUI;

    // 与后端 utils/validators.py 保持一致
    var USERNAME_PATTERN = /^[A-Za-z0-9_]{3,32}$/;
    var EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

    function query(name) {
        return new URLSearchParams(window.location.search).get(name);
    }

    // 只允许站内相对路径，避免开放重定向
    function safeNextTarget(value) {
        if (!value || value.charAt(0) !== '/' || value.charAt(1) === '/' || value.indexOf('\\') !== -1) {
            return null;
        }
        return value;
    }

    function loginUrl() {
        return document.body.getAttribute('data-login-url') || '/login';
    }

    function validateUsername(value) {
        if (!value) {
            return '请输入用户名';
        }
        if (!USERNAME_PATTERN.test(value)) {
            return '用户名必须为 3-32 位字母、数字或下划线';
        }
        return '';
    }

    function validatePassword(value) {
        if (!value) {
            return '请输入密码';
        }
        if (value.length < 8 || value.length > 128) {
            return '密码长度必须为 8-128 位';
        }
        if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
            return '密码必须同时包含字母和数字';
        }
        return '';
    }

    function validateEmail(value) {
        if (!value) {
            return '';
        }
        if (value.length > 254 || !EMAIL_PATTERN.test(value)) {
            return '邮箱格式不正确';
        }
        return '';
    }

    function validateNickname(value) {
        if (!value) {
            return '';
        }
        if (value.length > 64) {
            return '昵称长度必须为 1-64 位';
        }
        return '';
    }

    function initPasswordToggles() {
        Array.prototype.forEach.call(document.querySelectorAll('[data-toggle-password]'), function (button) {
            button.addEventListener('click', function () {
                var wrapper = button.closest('.input-with-action');
                var input = wrapper ? wrapper.querySelector('input') : null;
                if (!input) {
                    return;
                }
                var show = input.type === 'password';
                input.type = show ? 'text' : 'password';
                button.textContent = show ? '隐藏' : '显示';
                button.setAttribute('aria-pressed', show ? 'true' : 'false');
                button.setAttribute('aria-label', show ? '隐藏密码' : '显示密码');
            });
        });
    }

    function initLogin() {
        var form = document.querySelector('[data-login-form]');
        if (!form) {
            return;
        }
        var alertBox = document.querySelector('[data-auth-alert]');
        var submit = form.querySelector('[data-submit]');
        var usernameInput = form.querySelector('[name="username"]');
        var prefilled = query('username');
        if (prefilled && usernameInput && !usernameInput.value) {
            usernameInput.value = prefilled;
        }
        if (query('registered') === '1') {
            ui.showAlert(alertBox, '注册成功，请使用新账号登录。', 'success');
        }

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            ui.clearFieldErrors(form);
            ui.hideAlert(alertBox);

            var username = (form.querySelector('[name="username"]').value || '').trim();
            var password = form.querySelector('[name="password"]').value || '';
            var usernameError = validateUsername(username);
            var passwordError = validatePassword(password);
            if (usernameError) {
                ui.setFieldError(form, 'username', usernameError);
            }
            if (passwordError) {
                ui.setFieldError(form, 'password', passwordError);
            }
            if (usernameError || passwordError) {
                return;
            }

            ui.setBusy(submit, true, '登录中…');
            api.post('/api/login', { username: username, password: password }).then(function (profile) {
                // 登录成功后后端会重建 Session，必须重新获取 CSRF Token
                return api.refreshCsrfToken().then(function () {
                    return profile;
                });
            }).then(function (profile) {
                var name = (profile && (profile.nickname || profile.username)) || username;
                ui.toast('欢迎回来，' + name, 'success');
                var next = safeNextTarget(query('next'));
                window.setTimeout(function () {
                    window.location.assign(next || '/');
                }, 300);
            }).catch(function (error) {
                ui.setBusy(submit, false);
                if (error.status === 401) {
                    ui.showAlert(alertBox, error.message || '用户名或密码错误');
                    ui.setFieldError(form, 'password', '请检查用户名和密码');
                    return;
                }
                if (error.status === 429) {
                    ui.showAlert(alertBox, error.message || '登录失败次数过多，请稍后再试');
                    return;
                }
                ui.showAlert(alertBox, error.message || '登录失败，请稍后重试');
            });
        });
    }

    function initRegister() {
        var form = document.querySelector('[data-register-form]');
        if (!form) {
            return;
        }
        var alertBox = document.querySelector('[data-auth-alert]');
        var submit = form.querySelector('[data-submit]');

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            ui.clearFieldErrors(form);
            ui.hideAlert(alertBox);

            var username = (form.querySelector('[name="username"]').value || '').trim();
            var nickname = (form.querySelector('[name="nickname"]').value || '').trim();
            var email = (form.querySelector('[name="email"]').value || '').trim();
            var password = form.querySelector('[name="password"]').value || '';
            var confirmPassword = form.querySelector('[name="password_confirm"]').value || '';

            var errors = {
                username: validateUsername(username),
                nickname: validateNickname(nickname),
                email: validateEmail(email),
                password: validatePassword(password)
            };
            if (!confirmPassword) {
                errors.password_confirm = '请再次输入密码';
            } else if (confirmPassword !== password) {
                errors.password_confirm = '两次输入的密码不一致';
            }

            var hasError = false;
            Object.keys(errors).forEach(function (field) {
                if (errors[field]) {
                    hasError = true;
                    ui.setFieldError(form, field, errors[field]);
                }
            });
            if (hasError) {
                return;
            }

            var payload = { username: username, password: password };
            if (nickname) {
                payload.nickname = nickname;
            }
            if (email) {
                payload.email = email;
            }

            ui.setBusy(submit, true, '注册中…');
            api.post('/api/register', payload).then(function (profile) {
                ui.toast('注册成功，请登录', 'success');
                var target = loginUrl() + '?registered=1&username=' + encodeURIComponent(
                    (profile && profile.username) || username
                );
                window.setTimeout(function () {
                    window.location.assign(target);
                }, 400);
            }).catch(function (error) {
                ui.setBusy(submit, false);
                if (error.status === 409) {
                    ui.showAlert(alertBox, error.message || '用户名已存在');
                    ui.setFieldError(form, 'username', '该用户名已被注册，请换一个');
                    return;
                }
                if (error.status === 400) {
                    ui.showAlert(alertBox, error.message || '注册信息不符合要求');
                    return;
                }
                ui.showAlert(alertBox, error.message || '注册失败，请稍后重试');
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var page = document.body.getAttribute('data-page');
        initPasswordToggles();
        if (page === 'login') {
            initLogin();
        } else if (page === 'register') {
            initRegister();
        }
    });
})(window, document);
