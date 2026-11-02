"""交互式创建首个管理员，不在代码中保存或输出密码。"""

import getpass
import sys

from werkzeug.security import check_password_hash

from app import create_app
from database.connection import db_transaction, get_db, utc_now
from database.users import add_audit_log, find_user_by_username


def main() -> int:
    username = input("请输入已有用户的用户名: ").strip()
    password = getpass.getpass("请输入该用户密码: ")
    app = create_app()
    with app.app_context():
        database = get_db()
        user = find_user_by_username(database, username)
        if user is None or not check_password_hash(user["password_hash"], password):
            print("用户名或密码验证失败。")
            return 1
        if user["role"] == "admin":
            print("该用户已经是管理员。")
            return 0
        with db_transaction():
            database.execute(
                "UPDATE users SET role = 'admin', updated_at = ? WHERE id = ?",
                (utc_now(), user["id"]),
            )
            add_audit_log(
                database,
                None,
                "admin_initialized",
                user["id"],
                {"username": user["username"]},
            )
        print("管理员初始化成功。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
