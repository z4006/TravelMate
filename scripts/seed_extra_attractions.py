"""补充演示景点数据（幂等）。

成员 C 的 seed_initial_attractions() 只提供 5 条数据，不满足任务书
"至少 15 条" 的要求。本脚本在其基础上追加 15 条，共 20 条，
不修改 database/attractions.py，重复执行不会产生重复记录。

用法：
    .venv/bin/python -m scripts.seed_extra_attractions
"""

from app import create_app
from database.attractions import migrate_attractions, seed_initial_attractions
from database.connection import db_transaction, utc_now

# (名称, slug, 分类 slug, 城市, 地址, 简介, 票价(分), 开放时间)
_EXTRA_ATTRACTIONS = (
    (
        "秦始皇兵马俑博物馆",
        "terracotta-army",
        "historical",
        "西安市",
        "陕西省西安市临潼区秦陵北路",
        "以秦始皇陵陪葬坑和陶俑群闻名的遗址博物馆。",
        12000,
        "08:30-17:00",
    ),
    (
        "大雁塔",
        "giant-wild-goose-pagoda",
        "historical",
        "西安市",
        "陕西省西安市雁塔区雁塔路",
        "唐代佛教建筑遗存，西安标志性古迹之一。",
        5000,
        "08:00-18:00",
    ),
    (
        "中山陵",
        "sun-yat-sen-mausoleum",
        "historical",
        "南京市",
        "江苏省南京市玄武区紫金山南麓",
        "位于紫金山南麓的近代纪念性建筑群。",
        0,
        "08:30-17:00",
    ),
    (
        "拙政园",
        "humble-administrators-garden",
        "historical",
        "苏州市",
        "江苏省苏州市姑苏区东北街 178 号",
        "苏州古典园林代表，世界文化遗产。",
        8000,
        "07:30-17:30",
    ),
    (
        "岳麓书院",
        "yuelu-academy",
        "historical",
        "长沙市",
        "湖南省长沙市岳麓区麓山南路",
        "中国古代四大书院之一，坐落于岳麓山下。",
        5000,
        "08:00-17:30",
    ),
    (
        "桂林漓江",
        "li-river",
        "natural",
        "桂林市",
        "广西桂林市漓江风景名胜区",
        "以喀斯特峰林和江水景观著称的风景名胜区。",
        21000,
        "08:00-17:00",
    ),
    (
        "黄山风景区",
        "huangshan-scenic-area",
        "natural",
        "黄山市",
        "安徽省黄山市黄山区",
        "以奇松、怪石、云海、温泉闻名的山岳景区。",
        19000,
        "06:30-16:30",
    ),
    (
        "崂山",
        "laoshan",
        "natural",
        "青岛市",
        "山东省青岛市崂山区",
        "黄海之滨的山岳景区，兼具海景与道教文化。",
        9000,
        "07:00-17:00",
    ),
    (
        "鼓浪屿",
        "gulangyu",
        "natural",
        "厦门市",
        "福建省厦门市思明区鼓浪屿",
        "以海岛风光和近代建筑群闻名的旅游景区。",
        10000,
        "全天开放",
    ),
    (
        "洱海",
        "erhai-lake",
        "natural",
        "大理市",
        "云南省大理白族自治州大理市",
        "高原湖泊，环湖分布着多个白族村落。",
        0,
        "全天开放",
    ),
    (
        "广州长隆欢乐世界",
        "chimelong-paradise",
        "theme-park",
        "广州市",
        "广东省广州市番禺区迎宾路",
        "大型主题乐园，包含多种机动游乐设施。",
        25000,
        "09:30-18:00",
    ),
    (
        "北京环球影城",
        "universal-beijing-resort",
        "theme-park",
        "北京市",
        "北京市通州区京哈高速与东六环交汇处",
        "以电影主题为核心的大型主题公园。",
        41800,
        "09:00-20:00",
    ),
    (
        "成都大熊猫繁育研究基地",
        "chengdu-panda-base",
        "natural",
        "成都市",
        "四川省成都市成华区熊猫大道 1375 号",
        "以大熊猫繁育研究和科普展示为主的基地。",
        5500,
        "07:30-18:00",
    ),
    (
        "宽窄巷子",
        "kuanzhai-alley",
        "historical",
        "成都市",
        "四川省成都市青羊区金河路口",
        "由宽巷子、窄巷子和井巷子组成的清代古街街区。",
        0,
        "全天开放",
    ),
    (
        "亚龙湾",
        "yalong-bay",
        "natural",
        "三亚市",
        "海南省三亚市吉阳区亚龙湾国家旅游度假区",
        "以沙滩和海水质量著称的热带海滨度假区。",
        0,
        "全天开放",
    ),
)


def seed_extra_attractions(database) -> int:
    """幂等追加景点数据，返回本次新增的条数。"""

    category_ids = {
        row["slug"]: row["id"]
        for row in database.execute(
            "SELECT id, slug FROM attraction_categories"
        ).fetchall()
    }
    now = utc_now()
    inserted = 0
    for (
        name,
        slug,
        category_slug,
        city,
        address,
        description,
        price_cents,
        opening_hours,
    ) in _EXTRA_ATTRACTIONS:
        category_id = category_ids.get(category_slug)
        if category_id is None:
            raise RuntimeError(
                f"缺少分类 {category_slug}，请先运行 scripts.seed_attractions"
            )
        cursor = database.execute(
            "INSERT INTO attractions "
            "(name, slug, category_id, city, address, description, "
            "ticket_price_cents, opening_hours, image_url, status, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'active', ?, ?) "
            "ON CONFLICT(slug) DO NOTHING",
            (
                name,
                slug,
                category_id,
                city,
                address,
                description,
                price_cents,
                opening_hours,
                now,
                now,
            ),
        )
        inserted += cursor.rowcount
    return inserted


def main() -> None:
    app = create_app(init_database=False)
    with app.app_context():
        with db_transaction() as database:
            migrate_attractions(database)
            # 先写入成员 C 的基础数据，再追加本脚本的补充数据
            seed_initial_attractions(database)
            added = seed_extra_attractions(database)
        total = database.execute("SELECT COUNT(*) FROM attractions").fetchone()[0]
    print(f"本次新增 {added} 条，当前景点总数：{total}")


if __name__ == "__main__":
    main()