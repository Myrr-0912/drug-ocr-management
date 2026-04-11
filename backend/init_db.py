"""
数据库初始化脚本 - 首次运行时执行

使用方法:
    python init_db.py --password 你的MySQL密码

如果 root 没有密码:
    python init_db.py
"""
import argparse
import pymysql


def create_database(host: str, user: str, password: str, db_name: str) -> None:
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
            print(f"✓ 数据库 '{db_name}' 已就绪")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化 MySQL 数据库")
    parser.add_argument("--host", default="localhost", help="MySQL 主机")
    parser.add_argument("--user", default="root", help="MySQL 用户名")
    parser.add_argument("--password", default="", help="MySQL 密码")
    parser.add_argument("--db", default="drug_ocr_db", help="数据库名称")
    args = parser.parse_args()

    create_database(args.host, args.user, args.password, args.db)
    print("接下来请修改 .env 文件中的 DB_PASSWORD，然后运行: alembic upgrade head")
